/* Exercise the actual Finished calculator and handshake callers. The record
   boundary is stubbed so failures must occur before any peer I/O or advance. */
#include "PolarSSL/ssl_tls.c"

static int allocation, fail_at, live, reads, writes;
static unsigned char peer_finished[12];
static unsigned checks;

#define CHECK(condition) do { ++checks; if (!(condition)) { \
    fprintf(stderr, "TLS Finished check failed at line %d: %s\n", \
            __LINE__, #condition); exit(1); } } while (0)

void *mbedtls_calloc(size_t count, size_t size)
{
    void *p;
    if (++allocation == fail_at) return NULL;
    p = calloc(count, size);
    if (p) ++live;
    return p;
}
void mbedtls_free(void *p) { if (p) --live; free(p); }

void mbedtls_ssl_update_out_pointers(mbedtls_ssl_context *ssl,
                                    mbedtls_ssl_transform *transform)
{ (void)ssl; (void)transform; }
int mbedtls_ssl_read_record(mbedtls_ssl_context *ssl, unsigned update)
{
    (void)update; ++reads;
    ssl->in_msgtype = MBEDTLS_SSL_MSG_HANDSHAKE;
    ssl->in_hslen = 16;
    ssl->in_msg[0] = MBEDTLS_SSL_HS_FINISHED;
    memcpy(ssl->in_msg + 4, peer_finished, 12);
    return 0;
}
int mbedtls_ssl_write_handshake_msg(mbedtls_ssl_context *ssl)
{ (void)ssl; ++writes; return 0; }
int mbedtls_ssl_send_alert_message(mbedtls_ssl_context *ssl,
                                   unsigned char level, unsigned char message)
{ (void)ssl; (void)level; (void)message; return -1; }

/* Debug callbacks are intentionally silent; secrets never enter test output. */
void mbedtls_debug_print_msg(const mbedtls_ssl_context *ssl, int level,
                            const char *file, int line, const char *format, ...)
{ (void)ssl; (void)level; (void)file; (void)line; (void)format; }
void mbedtls_debug_print_ret(const mbedtls_ssl_context *ssl, int level,
                            const char *file, int line, const char *text, int ret)
{ (void)ssl; (void)level; (void)file; (void)line; (void)text; (void)ret; }
void mbedtls_debug_print_buf(const mbedtls_ssl_context *ssl, int level,
                            const char *file, int line, const char *text,
                            const unsigned char *buf, size_t n)
{ (void)ssl; (void)level; (void)file; (void)line; (void)text; (void)buf; (void)n; }

static void reset_allocator(int fail)
{ CHECK(live == 0); allocation = 0; fail_at = fail; reads = writes = 0; }
static int is_zero(const unsigned char *p, size_t n)
{ size_t i; for (i = 0; i < n; ++i) if (p[i]) return 0; return 1; }
static void unhex(const char *s, unsigned char out[12])
{
    unsigned v; size_t i;
    CHECK(strlen(s) == 24);
    for (i = 0; i < 12; ++i) {
        CHECK(sscanf(s + 2*i, "%2x", &v) == 1); out[i] = (unsigned char)v;
    }
}

static void exercise(int sha384, const unsigned char expected_client[12],
                     const unsigned char expected_server[12])
{
    static const unsigned char transcript[] = "client hello|server hello|certificate|key exchange";
    mbedtls_ssl_context ssl;
    mbedtls_ssl_config config;
    mbedtls_ssl_session session;
    mbedtls_ssl_handshake_params handshake;
    unsigned char output[64], input[64], calculated[12];
    int i, count, result;
    memset(&ssl, 0, sizeof(ssl)); memset(&config, 0, sizeof(config));
    memset(&session, 0, sizeof(session)); memset(&handshake, 0, sizeof(handshake));
    ssl.conf = &config; ssl.handshake = &handshake; ssl.session_negotiate = &session;
    ssl.minor_ver = MBEDTLS_SSL_MINOR_VERSION_3;
    ssl.out_msg = output; ssl.in_msg = input;
    config.endpoint = MBEDTLS_SSL_IS_CLIENT;
    for (i = 0; i < 48; ++i) session.master[i] = (unsigned char)i;
    if (sha384) {
        mbedtls_sha512_init(&handshake.fin_sha512);
        CHECK(mbedtls_sha512_starts_ret(&handshake.fin_sha512, 1) == 0);
        CHECK(mbedtls_sha512_update_ret(&handshake.fin_sha512, transcript, sizeof(transcript)-1) == 0);
        handshake.calc_finished = ssl_calc_finished_tls_sha384;
        handshake.tls_prf = tls_prf_sha384;
    } else {
        mbedtls_sha256_init(&handshake.fin_sha256);
        CHECK(mbedtls_sha256_starts_ret(&handshake.fin_sha256, 0) == 0);
        CHECK(mbedtls_sha256_update_ret(&handshake.fin_sha256, transcript, sizeof(transcript)-1) == 0);
        handshake.calc_finished = ssl_calc_finished_tls_sha256;
        handshake.tls_prf = tls_prf_sha256;
    }
    reset_allocator(0);
    CHECK(handshake.calc_finished(&ssl, calculated, MBEDTLS_SSL_IS_CLIENT) == 0);
    CHECK(memcmp(calculated, expected_client, 12) == 0);
    count = allocation;
    CHECK(count > 0 && live == 0);
    reset_allocator(0);
    CHECK(handshake.calc_finished(&ssl, calculated, MBEDTLS_SSL_IS_SERVER) == 0);
    CHECK(memcmp(calculated, expected_server, 12) == 0);
    CHECK(live == 0);

    for (i = 1; i <= count; ++i) {
        reset_allocator(i); memset(calculated, 0xa5, sizeof(calculated));
        CHECK(handshake.calc_finished(&ssl, calculated, MBEDTLS_SSL_IS_SERVER) != 0);
        CHECK(is_zero(calculated, sizeof(calculated)) && live == 0);

        reset_allocator(i); memset(output, 0xa5, sizeof(output));
        ssl.state = MBEDTLS_SSL_CLIENT_FINISHED;
        result = mbedtls_ssl_write_finished(&ssl);
        CHECK(result != 0 && writes == 0 && reads == 0);
        CHECK(ssl.state == MBEDTLS_SSL_CLIENT_FINISHED);
        CHECK(ssl.session_out == NULL && ssl.out_msglen == 0);
        CHECK(is_zero(output + 4, 12) && live == 0);

        reset_allocator(i); ssl.state = MBEDTLS_SSL_SERVER_FINISHED;
        result = mbedtls_ssl_parse_finished(&ssl);
        CHECK(result != 0 && reads == 0 && writes == 0);
        CHECK(ssl.state == MBEDTLS_SSL_SERVER_FINISHED && live == 0);
    }

    reset_allocator(0); ssl.state = MBEDTLS_SSL_CLIENT_FINISHED;
    CHECK(mbedtls_ssl_write_finished(&ssl) == 0 && writes == 1);
    CHECK(ssl.state == MBEDTLS_SSL_CLIENT_FINISHED + 1 && ssl.out_msglen == 16);
    CHECK(memcmp(output + 4, expected_client, 12) == 0 && live == 0);
    reset_allocator(0); ssl.state = MBEDTLS_SSL_SERVER_FINISHED;
    memcpy(peer_finished, expected_server, 12);
    CHECK(mbedtls_ssl_parse_finished(&ssl) == 0 && reads == 1);
    CHECK(ssl.state == MBEDTLS_SSL_SERVER_FINISHED + 1 && live == 0);
    reset_allocator(0); ssl.state = MBEDTLS_SSL_SERVER_FINISHED;
    peer_finished[0] ^= 1;
    CHECK(mbedtls_ssl_parse_finished(&ssl) == MBEDTLS_ERR_SSL_BAD_HS_FINISHED);
    CHECK(ssl.state == MBEDTLS_SSL_SERVER_FINISHED && live == 0);
}

int main(int argc, char **argv)
{
    unsigned char expected[4][12]; int i;
    CHECK(sizeof(unsigned long) == 4 && sizeof(uint32_t) == 4 && sizeof(uint64_t) == 8);
    CHECK(argc == 5);
    for (i = 0; i < 4; ++i) unhex(argv[i+1], expected[i]);
    exercise(0, expected[0], expected[1]);
    exercise(1, expected[2], expected[3]);
    printf("TLS Finished: %u checks passed\n", checks);
    return 0;
}
