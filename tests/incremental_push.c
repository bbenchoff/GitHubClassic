/* Export real packs, then let independent Git validate their contents. */
#include "GHCore.c"
#include "GitBytes.c"
#include "GitStore.c"
#include "GitIndex.c"
#include "GitHistory.c"
#include "GitGraph.c"
#include "GitPush.c"

typedef struct {char *path;unsigned char *data;size_t length,reads;} Entry;
typedef struct {Entry files[512];size_t count;const char *failPath;int failError;} Store;
static unsigned checks;
#define CHECK(x) do {++checks;if(!(x)){fprintf(stderr,"incremental_push:%d: %s\n",__LINE__,#x);exit(1);}} while(0)
static Entry *lookup(Store *s,const char *path) {
    size_t i;for(i=0;i<s->count;++i)if(!strcmp(s->files[i].path,path))return s->files+i;return NULL;
}
static int read_entry(void *context,const char *path,unsigned char **data,size_t *length) {
    Entry *e=lookup(context,path);unsigned char *p;
    Store *s=context;if(s->failPath && !strcmp(s->failPath,path))return s->failError;
    if(!e)return GS_NOT_FOUND;p=malloc(e->length?e->length:1);if(!p)return GB_MEMORY;
    memcpy(p,e->data,e->length);*data=p;*length=e->length;++e->reads;return 0;
}
static int replace_entry(void *context,const char *path,const void *expected,size_t oldLength,const void *data,size_t length) {
    Store *s=context;Entry *e=lookup(s,path);unsigned char *p;
    if((!expected && e)||(expected && (!e||e->length!=oldLength||memcmp(e->data,expected,oldLength))))return GS_CONFLICT;
    p=malloc(length?length:1);if(!p)return GB_MEMORY;memcpy(p,data,length);
    if(!e){CHECK(s->count<512);e=s->files+s->count++;memset(e,0,sizeof(*e));e->path=malloc(strlen(path)+1);CHECK(e->path);strcpy(e->path,path);}
    free(e->data);e->data=p;e->length=length;return 0;
}
static void commit(GSRepository *r,const unsigned char *parents,size_t parentCount,
                   const unsigned char *large,const char *side,const char *feature,unsigned char out[20]) {
    GIIndex index;unsigned char tree[20],info[32];GIInit(&index);memset(info,0,sizeof(info));memcpy(info,"TEXTCWIE",8);
    CHECK(GIStageBlob(r,&index,"large.bin",0100644,large,65536)==0);
    CHECK(GIStageBlob(r,&index,"shared.txt",0100644,"unchanged\n",10)==0);
    if(side)CHECK(GIStageBlob(r,&index,"side.txt",0100644,side,strlen(side))==0);
    if(feature)CHECK(GIStageMac(r,&index,"src/caf\xc3\xa9.c",feature,strlen(feature),info,"resource",8)==0);
    CHECK(GIWriteTree(r,&index,tree)==0);
    CHECK(GSWriteCommitObject(r,tree,parents,parentCount,"Fixture <test@example.invalid>",
                             "Fixture <test@example.invalid>","1","+0000","Fixture\n",out)==0);
    GIFree(&index);
}
static int file_read(void *context,size_t offset,void *p,size_t n) {
    FILE *f=context;return fseek(f,(long)offset,SEEK_SET)||fread(p,1,n,f)!=n?GS_IO:0;
}
static int file_write(void *context,size_t offset,const void *p,size_t n) {
    FILE *f=context;return fseek(f,(long)offset,SEEK_SET)||fwrite(p,1,n,f)!=n?GS_IO:0;
}
static int cancel(void *context,size_t count){(void)context;(void)count;return -177;}
static void export_bytes(const char *directory,const char *name,const void *p,size_t n) {
    char path[1024];FILE *f;CHECK(strlen(directory)+strlen(name)+2<sizeof(path));
    sprintf(path,"%s/%s",directory,name);f=fopen(path,"wb");CHECK(f);CHECK(fwrite(p,1,n,f)==n);CHECK(!fclose(f));
}
int main(int argc,char **argv) {
    Store *store=calloc(1,sizeof(*store));GSRepository repo;
    unsigned char large[65536],tip[20],base[20],a[20],b[20],parents[40],missing[20];
    unsigned char *full=NULL,*delta=NULL,*old=NULL,*same=NULL,*trial=NULL,block[16384];
    size_t fullLength=0,deltaLength=0,oldLength=0,sameLength=0,n=0,i,at,amount;
    GVLimits limits={4096,2097152,16777216};GVResult graph;GUFileIO io;FILE *file;char path[1024],hex[41],baseHex[41],basePath[64];Entry *baseEntry;
    CHECK(argc==2 && store);repo.context=store;repo.read=read_entry;repo.replace=replace_entry;
    memset(large,0x5a,sizeof(large));memset(tip,0,20);
    for(i=0;i<20;++i){large[i]=(unsigned char)i;commit(&repo,i?tip:NULL,i?1:0,large,NULL,NULL,a);memcpy(tip,a,20);}
    memcpy(base,tip,20);commit(&repo,base,1,large,"side\n",NULL,a);commit(&repo,base,1,large,NULL,"int main(void) { return 0; }\n",b);
    memcpy(parents,a,20);memcpy(parents+20,b,20);commit(&repo,parents,2,large,"side\n","int main(void) { return 0; }\n",tip);
    CHECK(GUPackBuild(&repo,tip,&limits,16777216,NULL,NULL,&full,&fullLength,&graph)==0);
    export_bytes(argv[1],"full.pack",full,fullLength);
    CHECK(GUPackBuild(&repo,base,&limits,16777216,NULL,NULL,&old,&oldLength,&graph)==0);
    export_bytes(argv[1],"base.pack",old,oldLength);
    for(i=0;i<store->count;++i)store->files[i].reads=0;
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,16777216,NULL,NULL,&delta,&deltaLength,&graph)==0);
    CHECK(graph.objects>0 && deltaLength<fullLength/10);
    for(i=0;i<store->count;++i)CHECK(store->files[i].reads==1);
    export_bytes(argv[1],"incremental.pack",delta,deltaLength);
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,deltaLength,NULL,NULL,&trial,&n,&graph)==0);
    CHECK(n==deltaLength && !memcmp(trial,delta,n));free(trial);trial=(unsigned char *)1;n=123;
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,deltaLength-1,NULL,NULL,&trial,&n,&graph)==GB_SPACE);
    CHECK(!trial && !n && !graph.objects);
    GSObjectPath(base,basePath);store->failPath=basePath;store->failError=GS_IO;
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,16777216,NULL,NULL,&trial,&n,&graph)==GS_IO);
    CHECK(!trial && !n && !graph.objects);
    store->failError=GS_NOT_FOUND;
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,16777216,NULL,NULL,&trial,&n,&graph)==GS_NOT_FOUND);
    CHECK(!trial && !n && !graph.objects);store->failPath=NULL;
    baseEntry=lookup(store,basePath);CHECK(baseEntry && baseEntry->length);
    baseEntry->data[baseEntry->length-1]^=1;
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,16777216,NULL,NULL,&trial,&n,&graph)!=0);
    CHECK(!trial && !n && !graph.objects);baseEntry->data[baseEntry->length-1]^=1;
    CHECK(GUPackBuild(&repo,tip,&limits,deltaLength,NULL,NULL,&trial,&n,&graph)==GB_SPACE);
    CHECK(!trial && !n && !graph.objects);
    CHECK(GUPackBuildSince(&repo,tip,base,&limits,16777216,cancel,NULL,&trial,&n,&graph)==-177);
    CHECK(!trial && !n && !graph.objects);
    memset(missing,0x42,sizeof(missing));
    CHECK(GUPackBuildSince(&repo,tip,missing,&limits,16777216,NULL,NULL,&trial,&n,&graph)==0);
    CHECK(n==fullLength && !memcmp(trial,full,n));free(trial);trial=NULL;
    CHECK(GUPackBuildSince(&repo,tip,tip,&limits,32,NULL,NULL,&same,&sameLength,&graph)==0);
    CHECK(sameLength==32 && graph.objects==0);export_bytes(argv[1],"same.pack",same,sameLength);
    sprintf(path,"%s/file.pack",argv[1]);file=fopen(path,"w+b");CHECK(file);memset(&io,0,sizeof(io));io.context=file;io.read=file_read;io.write=file_write;
    CHECK(GUPackWriteSince(&repo,tip,base,&limits,16777216,NULL,NULL,&io,&n,&graph)==0);
    CHECK(n==deltaLength);for(at=0;at<n;at+=amount){amount=n-at;if(amount>sizeof(block))amount=sizeof(block);CHECK(file_read(file,at,block,amount)==0);CHECK(!memcmp(block,delta+at,amount));}
    CHECK(!fclose(file));
    GBOIDFormat(tip,hex);GBOIDFormat(base,baseHex);sprintf(path,"%s/graph.txt",argv[1]);file=fopen(path,"wb");CHECK(file);
    fprintf(file,"%s\n%s\n%lu\n%lu\n",hex,baseHex,(unsigned long)fullLength,(unsigned long)deltaLength);CHECK(!fclose(file));
    free(full);free(delta);free(old);free(same);for(i=0;i<store->count;++i){free(store->files[i].path);free(store->files[i].data);}free(store);
    printf("Incremental push construction: %u checks passed\n",checks);return 0;
}
