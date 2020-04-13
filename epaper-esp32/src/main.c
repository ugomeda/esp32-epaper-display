#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include "esp_event_loop.h"
#include "nvs_flash.h"
#include "esp_http_client.h"
#include "driver/gpio.h"
#include "esp_sleep.h"
#include <epd.h>
#include <settings.h>

#define PIN_SPI_SCK_NUM GPIO_NUM_13
#define PIN_SPI_DIN_NUM GPIO_NUM_14
#define PIN_SPI_CS_NUM GPIO_NUM_15
#define PIN_SPI_BUSY_NUM GPIO_NUM_25
#define PIN_SPI_RST_NUM GPIO_NUM_26
#define PIN_SPI_DC_NUM GPIO_NUM_27

#define GOT_IPV4_BIT BIT(0)
#define CONNECTED_BITS (GOT_IPV4_BIT)
#define MAX_ETAG_SIZE 127

/**
 * WIFI MANAGEMENT
 */
static const char *WIFI_TAG = "wifi";
static EventGroupHandle_t s_connect_event_group;
static const char *s_connection_name;
static ip4_addr_t s_ip_addr;
bool wifi_disconnecting = false;

static void wifi_event_ip_available(void *arg, esp_event_base_t event_base,
                                    int32_t event_id, void *event_data)
{
    ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
    memcpy(&s_ip_addr, &event->ip_info.ip, sizeof(s_ip_addr));
    xEventGroupSetBits(s_connect_event_group, GOT_IPV4_BIT);
}

static void wifi_event_disconnect(void *arg, esp_event_base_t event_base,
                                  int32_t event_id, void *event_data)
{
    if (!wifi_disconnecting)
    {
        ESP_LOGI(WIFI_TAG, "Got disconnected, trying to reconnect...");
        ESP_ERROR_CHECK(esp_wifi_connect());
    }
}

static void wifi_initialize()
{
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED, &wifi_event_disconnect, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_ip_available, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    wifi_config_t wifi_config = {
        .sta = {
            .ssid = SETTINGS_WIFI_SSID,
            .password = SETTINGS_WIFI_PASSWORD,
        },
    };
    ESP_LOGI(WIFI_TAG, "Connecting to %s...", wifi_config.sta.ssid);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(ESP_IF_WIFI_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
    s_connection_name = SETTINGS_WIFI_SSID;
}

esp_err_t wifi_wait_until_connected(void)
{
    if (s_connect_event_group != NULL)
    {
        return ESP_ERR_INVALID_STATE;
    }
    s_connect_event_group = xEventGroupCreate();
    wifi_initialize();
    xEventGroupWaitBits(s_connect_event_group, CONNECTED_BITS, true, true, portMAX_DELAY);
    ESP_LOGI(WIFI_TAG, "Connected to %s", s_connection_name);
    ESP_LOGI(WIFI_TAG, "IPv4 address: " IPSTR, IP2STR(&s_ip_addr));

    return ESP_OK;
}

/**
 * SERVICE PULLING DATA FROM THE SERVER AND UPDATING THE DISPLAY
 */
static const char *UPDATER_TAG = "updater";
static const char *DISPLAY_TAG = "display";

// This is the ID of the image currently displayed.
// This is persisted across deep sleep mode.
RTC_DATA_ATTR char current_tag[MAX_ETAG_SIZE] = {0};

int64_t next_request_time = 0;

esp_err_t _http_event_handler(esp_http_client_event_t *evt)
{
    switch (evt->event_id)
    {
    case HTTP_EVENT_ON_HEADER:
        if (strcmp(evt->header_key, "ETag") == 0)
        {
            strncpy(current_tag, evt->header_value, MAX_ETAG_SIZE);
        }
        else if (strcmp(evt->header_key, "Cache-Control") == 0)
        {
            // Try to parse max_age=XXX
            if (strncmp(evt->header_value, "max-age=", 8) == 0)
            {
                long max_age = strtol(evt->header_value + 8, NULL, 10);
                if (errno != 0)
                {
                    ESP_LOGE(UPDATER_TAG, "Could not parse Cache-Control header \"%s\" : %s", evt->header_value, strerror(errno));
                    errno = 0;
                }
                else
                {
                    next_request_time = esp_timer_get_time() + max_age * 1e6;
                }
            }
        }
        break;
    default:
        break;
    }

    return ESP_OK;
}

esp_err_t update(char *url)
{
    // Set default time for next request, will be replaced by a Cache-Control
    // header if the request succeeds.
    next_request_time = esp_timer_get_time() + SETTINGS_DEFAULT_UPDATE_TIME * 1e6;

    // Initialize state
    int64_t timer = esp_timer_get_time();
    esp_err_t err = ESP_FAIL;

    // Initialize client
    ESP_LOGI(UPDATER_TAG, "Requesting new status");
    esp_http_client_config_t config = {
        .url = url,
        .event_handler = _http_event_handler,
    };
    esp_http_client_handle_t client = esp_http_client_init(&config);
    esp_http_client_set_header(client, "X-Display-ID", SETTINGS_DISPLAY_ID);
    esp_http_client_set_header(client, "Etag", current_tag);
    err = esp_http_client_open(client, 0);
    if (err != ESP_OK)
    {
        ESP_LOGE(UPDATER_TAG, "Error while connecting to server");
        ESP_ERROR_CHECK(esp_http_client_cleanup(client));

        return err;
    }

    // Check response
    int content_length = esp_http_client_fetch_headers(client);
    int status = esp_http_client_get_status_code(client);

    ESP_LOGI(UPDATER_TAG, "Status = %d, content_length = %d, ETag = %s", status, content_length, current_tag);

    if (status == 304)
    {
        ESP_LOGI(UPDATER_TAG, "Image did not change, skipping");
        ESP_ERROR_CHECK(esp_http_client_close(client));
        ESP_ERROR_CHECK(esp_http_client_cleanup(client));

        return ESP_OK;
    }

    if (status != 200)
    {
        ESP_LOGE(UPDATER_TAG, "Server returned code %d", status);
        ESP_ERROR_CHECK(esp_http_client_close(client));
        ESP_ERROR_CHECK(esp_http_client_cleanup(client));

        return ESP_FAIL;
    }

    // Allocate data
    ESP_LOGI(UPDATER_TAG, "Content_length = %d", content_length);

    size_t png_size = esp_http_client_get_content_length(client);
    char *data = malloc(png_size);
    if (data == NULL)
    {
        ESP_LOGE(UPDATER_TAG, "Could not allocate %d bytes to load PNG", png_size);
        ESP_ERROR_CHECK(esp_http_client_close(client));
        ESP_ERROR_CHECK(esp_http_client_cleanup(client));
        free(data);

        return ESP_ERR_NO_MEM;
    }

    // Read png
    int read_len = esp_http_client_read(client, data, png_size);
    if (read_len != png_size)
    {
        ESP_LOGE(UPDATER_TAG, "Expected to read %d bytes, but got %d", png_size, read_len);
        ESP_ERROR_CHECK(esp_http_client_close(client));
        ESP_ERROR_CHECK(esp_http_client_cleanup(client));
        free(data);

        return ESP_FAIL;
    }

    ESP_ERROR_CHECK(esp_http_client_close(client));
    ESP_ERROR_CHECK(esp_http_client_cleanup(client));

    ESP_LOGI(DISPLAY_TAG, "Passing the new image to EPD");

    EPD_before_load();
    err = EPD_load_image(data, png_size);
    free(data);
    if (err != ESP_OK)
    {
        ESP_LOGE(UPDATER_TAG, "Image display failed");
        EPD_shutdown();

        return err;
    }

    EPD_display();
    EPD_shutdown();

    float duration = (esp_timer_get_time() - timer) * 1.0e-6;
    ESP_LOGI(DISPLAY_TAG, "Update took %.2f seconds", duration);

    return ESP_OK;
}

static void update_task(void *pvParameters)
{
    // Generate the URL ans initialize client config
    char *url = malloc(strlen(SETTINGS_SERVER_URL) + strlen("get/") + 1);
    strcpy(url, SETTINGS_SERVER_URL);
    strcat(url, "get/");

    while (true)
    {
        esp_err_t err = update(url);
        if (err != ESP_OK)
        {
            ESP_LOGE(UPDATER_TAG, "Error while updating : %s", esp_err_to_name(err));

            // Assume current tag and next request are invalid
            current_tag[0] = '\0';
            next_request_time = esp_timer_get_time() + SETTINGS_DEFAULT_UPDATE_TIME * 1e6;
        }

        float waiting_time_us = next_request_time - esp_timer_get_time();

        // Go to deep sleep if next update is in more than 5 seconds
        if (next_request_time - esp_timer_get_time() > 5 * 1e6)
        {
            ESP_LOGI(UPDATER_TAG, "Going to deep sleep %.2f seconds until next update", waiting_time_us * 1e-6);

            // Tell the event listener we should no try to reconnect to the Wifi
            wifi_disconnecting = true;
            ESP_ERROR_CHECK(esp_wifi_stop());

            // Configure as shown in the documentation
            esp_sleep_enable_timer_wakeup(next_request_time - esp_timer_get_time());
            const int ext_wakeup_pin_1 = 2;
            const uint64_t ext_wakeup_pin_1_mask = 1ULL << ext_wakeup_pin_1;
            const int ext_wakeup_pin_2 = 4;
            const uint64_t ext_wakeup_pin_2_mask = 1ULL << ext_wakeup_pin_2;
            esp_sleep_enable_ext1_wakeup(ext_wakeup_pin_1_mask | ext_wakeup_pin_2_mask, ESP_EXT1_WAKEUP_ANY_HIGH);
            esp_deep_sleep_start();

            ESP_LOGE(UPDATER_TAG, "This should not be reachable !");
        }

        vTaskDelay(waiting_time_us * 1e-3 / portTICK_PERIOD_MS);
    }
}

/**
 * SERVICE UPDATING THE DISPLAY
 */
void app_main()
{
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND)
    {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize networking
    tcpip_adapter_init();

    // Initialize RTOS
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Wait until wifi is connected
    ESP_ERROR_CHECK(wifi_wait_until_connected());

    ESP_LOGI(DISPLAY_TAG, "Initializing EPD");
    EPD_initialize();

    xTaskCreate(&update_task, "update_task", 4096, NULL, 5, NULL);
}
