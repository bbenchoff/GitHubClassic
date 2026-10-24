/* Compare metadata encoding with Python's independent MacRoman codec. */
#include "GitText.c"
#include "GitPathMap.c"

static unsigned checks;
#define CHECK(x) do { ++checks; if(!(x)) { \
    fprintf(stderr,"commit_encoding:%d: %s\n",__LINE__,#x);exit(1); } } while(0)
static unsigned nibble(char c) {return c<='9'?(unsigned)(c-'0'):(unsigned)(c-'a'+10);}

int main(int argc,char **argv) {
    unsigned char input[256],expected[768],*out=NULL;
    size_t used=0,n=0,i,expectedLength;GEText roundtrip;
    CHECK(argc==2);expectedLength=strlen(argv[1])/2;
    CHECK(expectedLength<sizeof(expected) && !(strlen(argv[1])&1));
    for(i=0;i<expectedLength;++i)expected[i]=(unsigned char)((nibble(argv[1][i*2])<<4)|nibble(argv[1][i*2+1]));
    input[used++]='\t';input[used++]='\r';
    for(i=32;i<127;++i)input[used++]=(unsigned char)i;
    for(i=128;i<256;++i)input[used++]=(unsigned char)i;
    CHECK(GEMetadataUTF8(input,used,&out,&n)==0);
    CHECK(n==expectedLength && !memcmp(out,expected,n) && out[n]==0);
    CHECK(n<3 || memcmp(out,"\xef\xbb\xbf",3));
    GETextInit(&roundtrip);CHECK(GETextOpen(&roundtrip,out,n)==0);
    CHECK(roundtrip.length==used && !memcmp(roundtrip.text,input,used));
    GETextFree(&roundtrip);free(out);
    CHECK(GEMetadataUTF8("one\r\ntwo\rthree\nfour",19,&out,&n)==0);
    CHECK(n==18 && !memcmp(out,"one\ntwo\nthree\nfour",18) && !out[n]);free(out);
    for(i=0;i<32;++i) {
        if(i==9 || i==10 || i==13)continue;
        input[0]=(unsigned char)i;out=(unsigned char *)1;n=123;
        CHECK(GEMetadataUTF8(input,1,&out,&n)==GE_ENCODING);
        CHECK(!out && !n);
    }
    input[0]=127;CHECK(GEMetadataUTF8(input,1,&out,&n)==GE_ENCODING);
    CHECK(!out && !n);
    CHECK(GEMetadataUTF8(NULL,0,&out,&n)==0 && !n && out && !out[0]);free(out);
    CHECK(GEMetadataUTF8(NULL,1,&out,&n)==GB_BAD && !out && !n);
    CHECK(GEMetadataUTF8(input,GE_DISK_LIMIT+1,&out,&n)==GB_SPACE && !out && !n);
    printf("Commit metadata encoding: %u checks passed\n",checks);return 0;
}
