/* Plain Git files must survive native type mapping without inventing fork
   records. Also exercise the legacy baseline through real checkout plans. */
#include "GHCore.c"
#include "GitBytes.c"
#include "GitStore.c"
#include "GitIndex.c"
#include "GitHistory.c"
#include "GitRestore.c"
#include "GitPathMap.c"
#include "GitCheckout.c"
#include "GitCheckoutSession.c"
#include "GitCheckoutPlan.c"
#include "GitWorkspaceSave.c"
#include "GitWorkspaceRestorePlan.c"

typedef struct { char *path; unsigned char *data; size_t length; } Entry;
typedef struct { Entry files[256]; size_t count; } Store;
static unsigned checks;
#define CHECK(c) do { ++checks; if(!(c)) {fprintf(stderr,"Plain defaults failed at %d: %s\n",__LINE__,#c);exit(1);} } while(0)
static Entry *lookup(Store *s,const char *path) {
    size_t i;for(i=0;i<s->count;++i)if(!strcmp(s->files[i].path,path))return s->files+i;return NULL;
}
static int read_entry(void *context,const char *path,unsigned char **data,size_t *length) {
    Entry *e=lookup(context,path);unsigned char *p;
    if(!e)return GS_NOT_FOUND;p=malloc(e->length?e->length:1);if(!p)return GB_MEMORY;
    memcpy(p,e->data,e->length);*data=p;*length=e->length;return 0;
}
static int replace_entry(void *context,const char *path,const void *expected,size_t oldLength,
                         const void *data,size_t length) {
    Store *s=context;Entry *e=lookup(s,path);unsigned char *p;
    if((!expected && e) || (expected && (!e || e->length!=oldLength || memcmp(e->data,expected,oldLength))))return GS_CONFLICT;
    p=malloc(length?length:1);if(!p)return GB_MEMORY;memcpy(p,data,length);
    if(!e){CHECK(s->count<256);e=s->files+s->count++;e->path=malloc(strlen(path)+1);CHECK(e->path);strcpy(e->path,path);e->data=NULL;}
    free(e->data);e->data=p;e->length=length;return 0;
}
static int equal(void *unused,const char *a,const char *b) {(void)unused;return !strcmp(a,b);}
static void release(Store *s) {size_t i;for(i=0;i<s->count;++i){free(s->files[i].path);free(s->files[i].data);}}
static void commit(GSRepository *r,const unsigned char *parent,const char *text,int metadata,unsigned char out[20]) {
    GIIndex index;unsigned char tree[20],info[32];GIInit(&index);memset(info,0,32);
    if(metadata)CHECK(GIStageMac(r,&index,"sample.png",text,strlen(text),info,NULL,0)==0);
    else CHECK(GIStageBlob(r,&index,"sample.png",0100644,text,strlen(text))==0);
    CHECK(GIWriteTree(r,&index,tree)==0);
    CHECK(GSWriteCommitObject(r,tree,parent,parent?1:0,"Fixture <test@example.test>",
        "Fixture <test@example.test>","1","+0000","Fixture\n",out)==0);
    GIFree(&index);
}
static void apply_metadata(GSRepository *r,const GCTransaction *t) {
    size_t i;for(i=0;i<t->metadataCount;++i){const GCMetadata *m=t->metadata+i;
        CHECK(m->afterPresent);CHECK(r->replace(r->context,m->path,m->beforePresent?m->before:NULL,
            m->beforeLength,m->after,m->afterLength)==0);}
}
static void scenario(int legacy) {
    Store store;GSRepository r;GQPlan first,next;GQError why;GPMap map;
    GQWork work;unsigned char a[20],b[20],info[32],changed[32];GBWord mode;int forks;char key[96];
    memset(&store,0,sizeof(store));r.context=&store;r.read=read_entry;r.replace=replace_entry;
    GQInit(&first);GQInit(&next);GPInit(&map);memset(&work,0,sizeof(work));
    CHECK(GSInit(&r,"refs/heads/main")==0);commit(&r,NULL,"first",0,a);
    CHECK(GQToCommit(&r,"refs/heads/main",NULL,a,NULL,0,equal,NULL,&first,&why)==0);
    CHECK(first.transaction.fileCount==1 && first.mapping.count==1);
    GPDefaultFinderInfo(NULL,NULL,info);
    CHECK(!memcmp(info,"GHCf",4) && !memcmp(info+4,(unsigned char[28]){0},28));
    CHECK(!memcmp(first.transaction.files[0].newFile.finderInfo,info,32));
    CHECK(!memcmp(first.mapping.entries[0].finderInfo,info,32));
    CHECK(first.index.count==1 && first.mapping.entries[0].flags==0);
    apply_metadata(&r,&first.transaction);
    CHECK(GPLoad(&r,equal,NULL,&map)==0);
    work.path="sample.png";work.native=map.entries[0].native;work.file=first.transaction.files[0].newFile;
    if(legacy){memset(info,0,32);memcpy(info,"????????",8);memcpy(map.entries[0].finderInfo,info,32);
        CHECK(GPSave(&r,equal,NULL,&map)==0);memcpy(work.file.finderInfo,info,32);}
    CHECK(GPPlainFinderInfo(info));
    GPDefaultFinderInfo(&map,work.path,changed);CHECK(!memcmp(info,changed,32));
    CHECK(GPWorkPolicy(map.entries,GIFind(&first.index,work.path,0),info,0,&mode,&forks)==0 && !forks);
    memcpy(changed,info,32);changed[9]^=2;
    CHECK(!GPPlainFinderInfo(changed));
    CHECK(GPWorkPolicy(map.entries,GIFind(&first.index,work.path,0),changed,0,&mode,&forks)==0 && forks);
    CHECK(GPWorkPolicy(map.entries,GIFind(&first.index,work.path,0),info,1,&mode,&forks)==0 && forks);
    commit(&r,a,"second",0,b);
    CHECK(GQToCommit(&r,"refs/heads/main",a,b,&work,1,equal,NULL,&next,&why)==0);
    CHECK(next.transaction.fileCount==1);
    CHECK(!memcmp(next.transaction.files[0].oldFile.finderInfo,info,32));
    CHECK(!memcmp(next.transaction.files[0].newFile.finderInfo,info,32));
    CHECK(!memcmp(next.mapping.entries[0].finderInfo,info,32));
    CHECK(GIMacMetadataPath(work.path,key)==0 && !GIFind(&next.index,key,0));
    GQFree(&next);memcpy(work.file.finderInfo,changed,32);
    CHECK(GQToCommit(&r,"refs/heads/main",a,b,&work,1,equal,NULL,&next,&why)!=0 && why.reason==GQ_DIRTY);
    GPFree(&map);GQFree(&first);GQFree(&next);release(&store);
}
static void explicit_zero_metadata(void) {
    Store store;GSRepository r;GQPlan plan;GQError why;unsigned char tip[20],zero[32];
    memset(&store,0,sizeof(store));r.context=&store;r.read=read_entry;r.replace=replace_entry;
    GQInit(&plan);memset(zero,0,32);CHECK(GSInit(&r,"refs/heads/main")==0);commit(&r,NULL,"explicit",1,tip);
    CHECK(GQToCommit(&r,"refs/heads/main",NULL,tip,NULL,0,equal,NULL,&plan,&why)==0);
    CHECK(plan.transaction.fileCount==1 && !memcmp(plan.transaction.files[0].newFile.finderInfo,zero,32));
    CHECK(plan.mapping.entries[0].flags==GP_FORKS && !memcmp(plan.mapping.entries[0].finderInfo,zero,32));
    GQFree(&plan);release(&store);
}
static void restored_legacy_defaults(void) {
    Store store;GSRepository r;GIIndex index;GQPlan first,next;GQError why;
    GPMap current,original;GQWork work[2];GQProtection selected;
    const char *paths[1]={"sample.png"};unsigned char tree[20],tip[20],*encoded=NULL;
    unsigned char legacy[32];size_t n=0;const GPEntry *retained;
    memset(&store,0,sizeof(store));r.context=&store;r.read=read_entry;r.replace=replace_entry;
    GIInit(&index);GQInit(&first);GQInit(&next);GPInit(&current);GPInit(&original);
    memset(legacy,0,32);memcpy(legacy,"????????",8);memset(work,0,sizeof(work));
    CHECK(GSInit(&r,"refs/heads/main")==0);
    CHECK(GIStageBlob(&r,&index,"sample.png",0100644,"one",3)==0);
    CHECK(GIStageBlob(&r,&index,"unrelated.ghx",0100644,"two",3)==0);
    CHECK(GIWriteTree(&r,&index,tree)==0);
    CHECK(GSWriteCommitObject(&r,tree,NULL,0,"Fixture <test@example.test>",
        "Fixture <test@example.test>","1","+0000","Fixture\n",tip)==0);
    CHECK(GQToCommit(&r,"refs/heads/main",NULL,tip,NULL,0,equal,NULL,&first,&why)==0);
    apply_metadata(&r,&first.transaction);CHECK(GPLoad(&r,equal,NULL,&current)==0);
    CHECK(current.count==2);memcpy(current.entries[1].finderInfo,legacy,32);
    CHECK(GPSave(&r,equal,NULL,&current)==0);
    CHECK(GPEncode(&current,equal,NULL,&encoded,&n)==0);
    CHECK(GPParse(encoded,n,equal,NULL,&original)==0);free(encoded);
    free(original.entries[1].path);free(original.entries[1].native);original.count=1;
    memcpy(original.entries[0].finderInfo,legacy,32);
    work[0].path="sample.png";work[0].native=current.entries[0].native;
    work[0].file=first.transaction.files[0].newFile;
    work[1].path="unrelated.ghx";work[1].native=current.entries[1].native;
    work[1].file=first.transaction.files[1].newFile;memcpy(work[1].file.finderInfo,legacy,32);
    selected.paths=paths;selected.count=1;selected.changed=0;
    CHECK(GQToCommitRestored(&r,"refs/heads/main",tip,tip,work,2,&selected,&original,
        equal,NULL,&next,&why)==0);
    CHECK(next.transaction.fileCount==1 && !strcmp(next.transaction.files[0].newPath,"sample.png"));
    CHECK(!memcmp(next.transaction.files[0].newFile.finderInfo,legacy,32));
    retained=GPFind(&next.mapping,"unrelated.ghx");
    CHECK(retained && !memcmp(retained->finderInfo,legacy,32) && !retained->flags);
    CHECK(next.index.count==2);
    GPFree(&original);GPFree(&current);GQFree(&first);GQFree(&next);GIFree(&index);release(&store);
}
int main(void) {
    CHECK(sizeof(GBWord)==4);scenario(0);scenario(1);explicit_zero_metadata();restored_legacy_defaults();
    printf("Plain Finder defaults: %u checks passed\n",checks);return 0;
}
