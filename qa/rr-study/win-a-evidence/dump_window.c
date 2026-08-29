#include <stdio.h>
#include <common/monitor.h>
#include <ft8/constants.h>

int main(void)
{
    monitor_config_t cfg = {
        .f_min = 200.0f, .f_max = 3000.0f, .sample_rate = 12000,
        .time_osr = 2, .freq_osr = 2, .protocol = FTX_PROTOCOL_FT8
    }; /* identical to BUILD.md's documented Monitor Configuration */
    monitor_t mon;
    monitor_init(&mon, &cfg);
    printf("nfft=%d\n", mon.nfft);
    for (int i = 0; i < 8; ++i)
        printf("window[%d]=%.9f\n", i, mon.window[i]);
    double sum = 0.0;
    for (int i = 0; i < mon.nfft; ++i)
        sum += mon.window[i];
    printf("sum=%.9f\n", sum);
    monitor_free(&mon);
    return 0;
}
