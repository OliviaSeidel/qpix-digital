/*
 * Copyright (C) 2017 - 2019 Xilinx, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 * 3. The name of the author may not be used to endorse or promote products
 *    derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
 * WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
 * SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
 * OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
 * IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
 * OF SUCH DAMAGE.
 *
 */

/* Connection handle for a UDP Client session */

#include "udp_perf_client.h"

extern struct netif udp_netif;
static struct udp_pcb *pcb[NUM_OF_PARALLEL_CLIENTS];
static struct perf_stats client;
#define FINISH	1
/* Report interval time in ms */
#define REPORT_INTERVAL_TIME (INTERIM_REPORT_INTERVAL * 1000)
/* End time in ms */
#define END_TIME (UDP_TIME_INTERVAL * 1000)


void udp_print_app_header(void)
{
	xil_printf("UDP client connecting to %s on port %d\r\n",
			UDP_SERVER_IP_ADDRESS, UDP_CONN_PORT);
	xil_printf("On Host: Run $iperf -s -i %d -u\r\n\r\n",
			INTERIM_REPORT_INTERVAL);
}

static void print_udp_conn_stats(void)
{
	xil_printf("[%3d] local %s port %d connected with ",
			client.client_id, inet_ntoa(udp_netif.ip_addr),
			pcb[0]->local_port);
	xil_printf("%s port %d\r\n",inet_ntoa(pcb[0]->remote_ip),
			pcb[0]->remote_port);
	xil_printf("[ ID] Interval\t\tTransfer   Bandwidth\n\r");
}

static void stats_buffer(char* outString,
		double data, enum measure_t type)
{
	int conv = KCONV_UNIT;
	const char *format;
	double unit = 1024.0;

	if (type == SPEED)
		unit = 1000.0;

	while (data >= unit && conv <= KCONV_GIGA) {
		data /= unit;
		conv++;
	}

	/* Fit data in 4 places */
	if (data < 9.995) { /* 9.995 rounded to 10.0 */
		format = "%4.2f %c"; /* #.## */
	} else if (data < 99.95) { /* 99.95 rounded to 100 */
		format = "%4.1f %c"; /* ##.# */
	} else {
		format = "%4.0f %c"; /* #### */
	}
	sprintf(outString, format, data, kLabel[conv]);
}

/* The report function of a UDP client session */
static void udp_conn_report(u64_t diff,
		enum report_type report_type)
{
	u64_t total_len;
	double duration, bandwidth = 0;
	char data[16], perf[16], time[64];

	if (report_type == INTER_REPORT) {
		total_len = client.i_report.total_bytes;
	} else {
		client.i_report.last_report_time = 0;
		total_len = client.total_bytes;
	}

	/* Converting duration from milliseconds to secs,
	 * and bandwidth to bits/sec .
	 */
	duration = diff / 1000.0; /* secs */
	if (duration)
		bandwidth = (total_len / duration) * 8.0;

	stats_buffer(data, total_len, BYTES);
	stats_buffer(perf, bandwidth, SPEED);
	/* On 32-bit platforms, xil_printf is not able to print
	 * u64_t values, so converting these values in strings and
	 * displaying results
	 */
	sprintf(time, "%4.1f-%4.1f sec",
			(double)client.i_report.last_report_time,
			(double)(client.i_report.last_report_time + duration));
	xil_printf("[%3d] %s  %sBytes  %sbits/sec\n\r", client.client_id,
			time, data, perf);

	if (report_type == INTER_REPORT)
		client.i_report.last_report_time += duration;
	else
		xil_printf("[%3d] sent %llu datagrams\n\r",
				client.client_id, client.cnt_datagrams);
}

static void reset_stats(void)
{
	client.client_id++;
	/* Print connection statistics */
	print_udp_conn_stats();
	/* Save start time for final report */
	client.start_time = get_time_ms();
	client.total_bytes = 0;
	client.cnt_datagrams = 0;

	/* Initialize Interim report parameters */
	client.i_report.start_time = 0;
	client.i_report.total_bytes = 0;
	client.i_report.last_report_time = 0;
}

#define ZYBO_LENGTH 0x00003fff // max length is 26 bits?
extern u32 data_buf[ZYBO_LENGTH];
void udp_packet_send(u16 size_t)
{
	u16 *payload;
	static u16 packet_id;
	u8_t i;
	u8_t retries = MAX_SEND_RETRY;
	struct pbuf *packet;
	err_t err;

	for (i = 0; i < NUM_OF_PARALLEL_CLIENTS; i++) {

		packet = pbuf_alloc(PBUF_TRANSPORT, size_t+2, PBUF_POOL);

		if (!packet) {
			xil_printf("error allocating pbuf to send\r\n");
			return;
		} else {
			memcpy(packet->payload, data_buf, size_t+2);
		}

		/* always increment the id */
		payload = (u16*) (packet->payload);
		payload[size_t / 2] = packet_id;

		while (retries) {
			err = udp_send(pcb[i], packet);
			if (err != ERR_OK) {
				xil_printf("Error on udp_send: %d\r\n", err);
				retries--;
				usleep(100);
			} else {
				client.total_bytes += size_t;
				client.cnt_datagrams++;
				client.i_report.total_bytes += size_t;
				break;
			}
		}

		pbuf_free(packet);

	}
	packet_id++;
}

/** Transmit data on a udp session if we meet a condition */
void udp_transfer_data(void)
{
	int i = 0;

	for (i = 0; i < NUM_OF_PARALLEL_CLIENTS; i++) {
		if (pcb[i] == NULL){
			xil_printf("UDP has no pcb here!\n\r");
			return;
		}
	}

	if (REPORT_INTERVAL_TIME) {
		u64_t now = get_time_ms();
		if (REPORT_INTERVAL_TIME) {
			if (client.i_report.start_time) {
				u64_t diff_ms = now - client.i_report.start_time;
				if (diff_ms >= REPORT_INTERVAL_TIME) {
					udp_conn_report(diff_ms, INTER_REPORT);
					client.i_report.start_time = 0;
					client.i_report.total_bytes = 0;
				}
			} else {
				client.i_report.start_time = now;
			}
		}
	}
}

// called from normal start_application, create a PCB to use to manage UDP transfers
void udp_start_application(void)
{
	err_t err;
	ip_addr_t remote_addr;
	u32_t i;

	err = inet_aton(UDP_SERVER_IP_ADDRESS, &remote_addr);
	if (!err) {
		xil_printf("Invalid Server IP address: %d\r\n", err);
		return;
	}

	for (i = 0; i < NUM_OF_PARALLEL_CLIENTS; i++) {
		/* Create Client PCB */
		pcb[i] = udp_new();
		if (!pcb[i]) {
			xil_printf("Error in PCB creation. out of memory\r\n");
			return;
		}

		err = udp_connect(pcb[i], &remote_addr, UDP_CONN_PORT);
		if (err != ERR_OK) {
			xil_printf("udp_client: Error on udp_connect: %d\r\n", err);
			udp_remove(pcb[i]);
			return;
		}
	}
	/* Wait for successful connection */
	usleep(10);
	reset_stats();
}
