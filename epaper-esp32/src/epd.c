#include "epd.h"

#define PIN_SPI_SCK_NUM GPIO_NUM_13
#define PIN_SPI_DIN_NUM GPIO_NUM_14
#define PIN_SPI_CS_NUM GPIO_NUM_15
#define PIN_SPI_BUSY_NUM GPIO_NUM_25
#define PIN_SPI_RST_NUM GPIO_NUM_26
#define PIN_SPI_DC_NUM GPIO_NUM_27

#define WHITE 0x03
#define RED 0x04
#define BLACK 0x00

#define BUFFER_SIZE 64

#define DISPLAY_WIDTH 640
#define DISPLAY_HEIGHT 384

static const char *EPD_TAG = "EPD";

// Maps the PNG palette to EPD's values
uint8_t PIX_MAPPING[4] = {BLACK, WHITE, RED, BLACK};

void EPD_initialize()
{
  ESP_ERROR_CHECK(gpio_set_direction(PIN_SPI_BUSY_NUM, GPIO_MODE_INPUT));

  gpio_config_t io_conf;
  io_conf.intr_type = GPIO_INTR_DISABLE;
  io_conf.mode = GPIO_MODE_OUTPUT;
  io_conf.pin_bit_mask = ((1ULL << 26) | (1ULL << 27) | (1ULL << 13) | (1ULL << 14) | (1ULL << 15));
  io_conf.pull_down_en = GPIO_PULLDOWN_ENABLE;
  io_conf.pull_up_en = GPIO_PULLUP_ENABLE;
  ESP_ERROR_CHECK(gpio_config(&io_conf));

  // Initialize GPIO values
  ESP_ERROR_CHECK(gpio_set_level(PIN_SPI_CS_NUM, 1));
  ESP_ERROR_CHECK(gpio_set_level(PIN_SPI_SCK_NUM, 0));
}

/* Waiting the e-Paper is ready for further instructions ---------------------*/
void EPD_WaitUntilIdle()
{
  while (gpio_get_level(PIN_SPI_BUSY_NUM) == 0)
  {
    vTaskDelay(100 / portTICK_PERIOD_MS);
  }
}

/* The procedure of sending a byte to e-Paper by SPI -------------------------*/
void EDP_send_byte(const char data)
{
  for (int i = 0; i < 8; i++)
  {
    gpio_set_level(PIN_SPI_DIN_NUM, ((0x80 >> i) & data) == 0 ? 0 : 1);
    gpio_set_level(PIN_SPI_SCK_NUM, 1);
    gpio_set_level(PIN_SPI_SCK_NUM, 0);
  }
}

/* Sending a byte as a command -----------------------------------------------*/
void EPD_SendCommand(const char command, const char *data, int data_len)
{
  gpio_set_level(PIN_SPI_CS_NUM, 0);
  gpio_set_level(PIN_SPI_DC_NUM, 0);
  EDP_send_byte(command);

  if (data_len > 0)
  {
    gpio_set_level(PIN_SPI_DC_NUM, 1);
    for (int i = 0; i < data_len; i++)
    {
      EDP_send_byte(data[i]);
    }
  }

  gpio_set_level(PIN_SPI_CS_NUM, 1);
}

void EPD_SendData(const char *data, int data_len)
{
  gpio_set_level(PIN_SPI_CS_NUM, 0);
  gpio_set_level(PIN_SPI_DC_NUM, 1);
  for (int i = 0; i < data_len; i++)
  {
    EDP_send_byte(data[i]);
  }
  gpio_set_level(PIN_SPI_CS_NUM, 1);
}

int EPD_7in5__init()
{
  // WAKE UP
  gpio_set_level(PIN_SPI_RST_NUM, 0);
  vTaskDelay(200 / portTICK_PERIOD_MS);

  gpio_set_level(PIN_SPI_RST_NUM, 1);
  vTaskDelay(200 / portTICK_PERIOD_MS);

  EPD_SendCommand(0x01, "\x37\x00", 2);     //POWER_SETTING
  EPD_SendCommand(0x00, "\xCF\x08", 2);     //PANEL_SETTING
  EPD_SendCommand(0x06, "\xC7\xCC\x28", 3); //BOOSTER_SOFT_START
  EPD_SendCommand(0x4, NULL, 0);            //POWER_ON
  EPD_WaitUntilIdle();

  EPD_SendCommand(0x30, "\x3C", 1);             //PLL_CONTROL
  EPD_SendCommand(0x41, "\x00", 1);             //TEMPERATURE_CALIBRATION
  EPD_SendCommand(0x50, "\x77", 1);             //VCOM_AND_DATA_INTERVAL_SETTING
  EPD_SendCommand(0x60, "\x22", 1);             //TCON_SETTING
  EPD_SendCommand(0x61, "\x02\x80\x01\x80", 4); //TCON_RESOLUTION
  EPD_SendCommand(0x82, "\x1E", 1);             //VCM_DC_SETTING: decide by LUT file
  EPD_SendCommand(0xE5, "\x03", 1);             //FLASH MODE

  EPD_SendCommand(0x10, NULL, 0); //DATA_START_TRANSMISSION_1
  vTaskDelay(2 / portTICK_PERIOD_MS);

  return 0;
}

void EPD_display()
{
  // Refresh
  EPD_SendCommand(0x12, NULL, 0); // DISPLAY_REFRESH
  vTaskDelay(100 / portTICK_PERIOD_MS);
  EPD_WaitUntilIdle();
}

void EPD_shutdown()
{
  // Sleep
  EPD_SendCommand(0x02, NULL, 0); // POWER_OFF
  EPD_WaitUntilIdle();
  EPD_SendCommand(0x07, "\xA5", 1); // DEEP_SLEEP
}

void EPD_loadImage(const uint8_t *image, const unsigned int width, const unsigned int height)
{
  char buffer[BUFFER_SIZE];
  int buffer_pos = 0;

  // 2-bit image, each byte contains 4 pixels
  for (uint32_t i = 0; i < width * height / 4; i++)
  {
    // each byte = 2 pixels
    uint8_t pix_1 = PIX_MAPPING[(image[i] & (0x03 << 6)) >> 6];
    uint8_t pix_2 = PIX_MAPPING[(image[i] & (0x03 << 4)) >> 4];
    uint8_t pix_3 = PIX_MAPPING[(image[i] & (0x03 << 2)) >> 2];
    uint8_t pix_4 = PIX_MAPPING[(image[i] & (0x03 << 0)) >> 0];

    buffer[buffer_pos++] = pix_1 << 4 | pix_2;
    buffer[buffer_pos++] = pix_3 << 4 | pix_4;

    if (buffer_pos == BUFFER_SIZE || i == width * height / 4)
    {
      EPD_SendData(buffer, buffer_pos);
      buffer_pos = 0;
    }
  }
}

void EPD_before_load()
{
  // Display image
  ESP_LOGI(EPD_TAG, "Booting up display");
  EPD_7in5__init();
}

esp_err_t EPD_load_image(const char *png, const int png_size)
{
  ESP_LOGI(EPD_TAG, "Received new PNG of size %d", png_size);

  // Decode image
  uint8_t *image;
  LodePNGState state;
  unsigned int width = 0;
  unsigned int height = 0;
  lodepng_state_init(&state);
  state.info_raw.colortype = LCT_PALETTE;
  state.info_raw.bitdepth = 2U;
  state.decoder.color_convert = 0;
  int error = lodepng_decode(&image, &width, &height, &state, (unsigned char *)png, png_size);
  if (error != 0)
  {
    free(image);
    lodepng_state_cleanup(&state);
    ESP_LOGE(EPD_TAG, "Error %u while decoding PNG: %s", error, lodepng_error_text(error));

    return ESP_FAIL;
  }

  // Check sanity
  if (width != DISPLAY_WIDTH || height != DISPLAY_HEIGHT)
  {
    free(image);
    lodepng_state_cleanup(&state);
    ESP_LOGE(EPD_TAG, "Display of size %dx%d, got image of %dx%d", DISPLAY_WIDTH, DISPLAY_HEIGHT, width, height);

    return ESP_FAIL;
  }

  ESP_LOGI(EPD_TAG, "Sending image");
  EPD_loadImage(image, width, height);
  lodepng_state_cleanup(&state);
  free(image);

  ESP_LOGI(EPD_TAG, "Done");

  return ESP_OK;
}
