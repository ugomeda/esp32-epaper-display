### Optimizations

#### Don't refresh the display is not required

The servers returns a header `ETag` containing an id of the image. This id is stored by
the client and sent on each request.

If the image did not change since the previous request, the status code returned will
be 304, so that the clients knows it should not update the display.


#### Don't request the server too frequently

The data is updated according to the `updateEvery` setting. Each request for the image returns
a header `Cache-Control": max-age=XXX` containing the number of seconds until the next request,
plus 20 seconds.

This allows the client to sleep the time required, and request the next image only when it
would be updated.

### Notes

- Conversion of SVG to monochrome PNG for the weather : `mogrify -format png -flatten -density 300 -monochrome *.svg && mogrify -format png -auto-level *.png`

### Attribution

- Weather icons : https://github.com/erikflowers/weather-icons
