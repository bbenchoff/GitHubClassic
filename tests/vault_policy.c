/* Credential policy and legacy envelope compatibility. All inputs synthetic. */
#include "GHVault.c"
#include "vault_vectors.h"

void *mbedtls_calloc(size_t n,size_t size) { return calloc(n,size); }
void mbedtls_free(void *p) { free(p); }

static unsigned checks;
#define CHECK(x) do { ++checks; if(!(x)) { \
    fprintf(stderr,"vault_policy:%d: %s\n",__LINE__,#x);exit(1); } } while(0)
static int cancel(void *context) { ++*(unsigned *)context; return 1; }

int main(void) {
    unsigned char pass[1025],random[GV_RANDOM],*out,*opened=NULL,key[32],*sealed=NULL;
    size_t n,openedLength=0,sealedLength=0,i;
    unsigned callbacks;
    memset(pass,'x',sizeof(pass));memset(random,0,sizeof(random));
    CHECK(!GVNewPassphraseValid(NULL,12));
    CHECK(!GVNewPassphraseValid(pass,0));
    CHECK(!GVNewPassphraseValid(pass,11));
    CHECK(GVNewPassphraseValid(pass,12));
    CHECK(GVNewPassphraseValid(pass,1024));
    CHECK(!GVNewPassphraseValid(pass,1025));
    for(i=0;i<12;++i) {
        out=(unsigned char *)1;n=123;callbacks=0;memset(key,0xa5,sizeof(key));
        CHECK(GVSealRemember("secret",6,pass,i,random,GV_MIN_ROUNDS,cancel,&callbacks,&out,&n,key)==GV_BAD);
        CHECK(out==(unsigned char *)1 && n==123 && !callbacks);
        CHECK(key[0]==0xa5 && key[31]==0xa5);
    }
    out=(unsigned char *)1;n=123;callbacks=0;
    CHECK(GVSeal("secret",6,pass,12,random,GV_MIN_ROUNDS,cancel,&callbacks,&out,&n)==GV_CANCEL);
    CHECK(callbacks==1 && out==(unsigned char *)1 && n==123);
    callbacks=0;
    CHECK(GVSeal("secret",6,pass,1024,random,GV_MIN_ROUNDS,cancel,&callbacks,&out,&n)==GV_CANCEL);
    CHECK(callbacks==1 && out==(unsigned char *)1 && n==123);
    /* New policy must not strand an existing short-passphrase vault. */
    CHECK(GVOpenRemember(legacy_vault,sizeof(legacy_vault),(const unsigned char *)"weak",4,
                         NULL,NULL,&opened,&openedLength,key)==0);
    CHECK(openedLength==25 && !memcmp(opened,"legacy test authorization",25));
    CHECK(!memcmp(key,legacy_key,32));
    GVClear(opened,openedLength);free(opened);opened=NULL;openedLength=0;
    CHECK(GVOpen(legacy_vault,sizeof(legacy_vault),(const unsigned char *)"wrong",5,
                 NULL,NULL,&opened,&openedLength)==GV_AUTH);
    CHECK(!opened && !openedLength);
    CHECK(GVSeal("new test authorization",22,pass,12,random,GV_MIN_ROUNDS,
                 NULL,NULL,&sealed,&sealedLength)==0);
    CHECK(GVOpen(sealed,sealedLength,pass,12,NULL,NULL,&opened,&openedLength)==0);
    CHECK(openedLength==22 && !memcmp(opened,"new test authorization",22));
    GVClear(opened,openedLength);free(opened);GVClear(sealed,sealedLength);free(sealed);
    GVClear(pass,sizeof(pass));GVClear(key,sizeof(key));
    printf("Vault policy: %u checks passed\n",checks);return 0;
}
