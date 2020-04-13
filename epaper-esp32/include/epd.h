#ifndef EPD_H
#define EPD_H

#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lodepng.h"

void EPD_initialize();
void EPD_before_load();
void EPD_display();
void EPD_shutdown();
esp_err_t EPD_load_image(const char *png, const int png_size);

#endif