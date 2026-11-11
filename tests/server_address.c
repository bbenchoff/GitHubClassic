/* Server addresses, stored server records and request paths. */
#include "GitBytes.c"
#include "GHCore.c"
#include "GitServer.c"

static unsigned checks;
#define CHECK(x) do { ++checks; if(!(x)) { \
    fprintf(stderr,"server_address:%d: %s\n",__LINE__,#x);exit(1); } } while(0)

static void accept(const char *url,int tls,const char *host,unsigned port,const char *prefix,
                   int dotGit,const char *user,const char *repository,const char *display) {
    GRServer s,again;char name[256],record[GR_RECORD_LIMIT+1],text[600],path[700];size_t n=0;
    CHECK(GRParseURL(url,&s,name)==0);
    CHECK(s.custom==1 && s.tls==tls && s.port==port && s.dotGit==dotGit);
    CHECK(!strcmp(s.host,host) && !strcmp(s.prefix,prefix) && !strcmp(s.user,user));
    CHECK(!strcmp(name,repository));
    CHECK(GRDisplay(&s,name,text,sizeof(text))==0 && !strcmp(text,display));
    CHECK(GRPack(&s,record,sizeof(record),&n)==0 && n<=GR_RECORD_LIMIT);
    CHECK(GRUnpack((const unsigned char *)record,n,&again)==0 && GRSame(&s,&again));
    CHECK(GRPath(&s,name,"info/refs?service=git-upload-pack",path,sizeof(path))==0);
    snprintf(text,sizeof(text),"%s/%s%s/info/refs?service=git-upload-pack",prefix,repository,dotGit?".git":"");
    CHECK(!strcmp(path,text));
    /* The display form without credentials parses back to the same server. */
    if(!user[0]) {
        CHECK(GRParseURL(display,&again,text)==0 && GRSame(&s,&again) && !strcmp(text,repository));
    }
}
static void refuse(const char *url) {
    GRServer s;char name[256];
    memset(&s,0x55,sizeof(s));strcpy(name,"unchanged");
    CHECK(GRParseURL(url,&s,name)==GB_BAD);
    CHECK(!name[0] || !strcmp(name,"unchanged"));
}
static void refuseRecord(const char *record) {
    GRServer s;
    CHECK(GRUnpack((const unsigned char *)record,strlen(record),&s)==GB_BAD);
}

int main(void) {
    GRServer github,s,other;char text[600],name[256],record[GR_RECORD_LIMIT+1],longURL[700];size_t n,i;

    accept("http://nas/git/project.git",0,"nas",80,"",1,"","git/project","http://nas/git/project.git");
    accept("http://192.168.0.16:3000/brian/tools",0,"192.168.0.16",3000,"",0,"","brian/tools",
           "http://192.168.0.16:3000/brian/tools");
    accept("https://Git.Example.ORG/team/app.git",1,"git.example.org",443,"",1,"","team/app",
           "https://git.example.org/team/app.git");
    accept("HTTPS://git.example.org:8443/scm/a/b/team/app.git/",1,"git.example.org",8443,"/scm/a/b",1,"",
           "team/app","https://git.example.org:8443/scm/a/b/team/app.git");
    accept("http://brian@nas:80/git/project.git",0,"nas",80,"",1,"brian","git/project",
           "http://nas/git/project.git");
    accept("https://first.last+ci@codeberg.org/owner/name",1,"codeberg.org",443,"",0,"first.last+ci",
           "owner/name","https://codeberg.org/owner/name");
    accept("http://h/~user/x/y.git",0,"h",80,"/~user",1,"","x/y","http://h/~user/x/y.git");

    refuse("");refuse("nas/git/project.git");refuse("ftp://nas/git/project.git");
    refuse("git://nas/git/project.git");refuse("ssh://git@nas/git/project.git");
    refuse("http://");refuse("http:///git/project.git");refuse("http://nas");refuse("http://nas/");
    refuse("http://nas/project.git");                 /* Needs two path parts. */
    refuse("http://nas/.git");refuse("http://nas/a/.git");
    refuse("http://user:secret@nas/git/project.git"); /* Never a password in the address. */
    refuse("http://@nas/git/project.git");
    refuse("http://nas:0/git/project.git");refuse("http://nas:65536/git/project.git");
    refuse("http://nas:/git/project.git");refuse("http://nas:12a/git/project.git");
    refuse("http://nas:123456/git/project.git");
    refuse("http://na_s/git/project.git");refuse("http://-nas/git/project.git");
    refuse("http://nas-/git/project.git");refuse("http://nas..local/git/project.git");
    refuse("http://[::1]/git/project.git");
    refuse("http://nas/git/project.git?x=1");refuse("http://nas/git/project.git#top");
    refuse("http://nas/git/pro ject.git");refuse("http://nas/a/../git/project.git");
    refuse("http://nas/a/./git/project.git");refuse("http://nas/a//git/project.git");
    refuse("http://nas/git/..");refuse("http://nas/%2e%2e/git/project.git");
    refuse("http://nas/git/project.git\r\nHost: other");
    /* Bounds: host 253, prefix 255, user 127. */
    strcpy(longURL,"http://");for(i=0;i<127;++i)strcat(longURL,"u");strcat(longURL,"@nas/a/b");
    CHECK(GRParseURL(longURL,&s,name)==0 && strlen(s.user)==127);
    strcpy(longURL,"http://");for(i=0;i<128;++i)strcat(longURL,"u");strcat(longURL,"@nas/a/b");refuse(longURL);
    strcpy(longURL,"http://");for(i=0;i<64;++i)strcat(longURL,"h");strcat(longURL,"/a/b");refuse(longURL);
    strcpy(longURL,"http://nas");for(i=0;i<127;++i)strcat(longURL,"/p");strcat(longURL,"p/a/b");
    CHECK(GRParseURL(longURL,&s,name)==0 && strlen(s.prefix)==255);
    strcat(longURL,"/c");refuse(longURL);

    /* GitHub is the absence of a record: its path and name are unchanged. */
    GRReset(&github);
    CHECK(GRPath(&github,"bbenchoff/GitHubClassic","git-upload-pack",text,sizeof(text))==0);
    CHECK(!strcmp(text,"/bbenchoff/GitHubClassic.git/git-upload-pack"));
    CHECK(GRHostHeader(&github,text,sizeof(text))==0 && !strcmp(text,"github.com"));
    CHECK(GRDisplay(&github,"bbenchoff/GitHubClassic",text,sizeof(text))==0 && !strcmp(text,"bbenchoff/GitHubClassic"));
    CHECK(GRPack(&github,record,sizeof(record),&n)==GB_BAD);
    CHECK(GRPath(&github,"not a repository","git-upload-pack",text,sizeof(text))==GB_BAD);
    CHECK(GRPath(&github,"a/b","git-upload-pack",text,8)==GB_BAD);

    CHECK(GRParseURL("http://nas:8080/git/project.git",&s,name)==0);
    CHECK(GRHostHeader(&s,text,sizeof(text))==0 && !strcmp(text,"nas:8080"));
    CHECK(GRPath(&s,name,"git-receive-pack",text,sizeof(text))==0 && !strcmp(text,"/git/project.git/git-receive-pack"));
    CHECK(GRPack(&s,record,sizeof(record),&n)==0);
    CHECK(!strcmp(record,"GHServer1\nhttp\nnas\n8080\n\n1\n\n"));
    CHECK(GRPack(&s,record,10,&n)==GB_BAD);
    CHECK(GRParseURL("https://nas:8080/git/project.git",&other,name)==0 && !GRSame(&s,&other));
    CHECK(GRParseURL("http://nas:8081/git/project.git",&other,name)==0 && !GRSame(&s,&other));
    CHECK(GRParseURL("http://nas:8080/git/project",&other,name)==0 && !GRSame(&s,&other));
    CHECK(GRParseURL("http://me@nas:8080/git/project.git",&other,name)==0 && !GRSame(&s,&other));
    CHECK(GRSame(&github,&github) && !GRSame(&github,&s) && !GRSame(&s,&github));

    refuseRecord("");refuseRecord("GHServer1\n");refuseRecord("GHServer2\nhttp\nnas\n80\n\n1\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n80\n\n1\n");            /* Missing field. */
    refuseRecord("GHServer1\nhttp\nnas\n80\n\n1\n\nextra\n");   /* Trailing data. */
    refuseRecord("GHServer1\ngopher\nnas\n80\n\n1\n\n");
    refuseRecord("GHServer1\nhttp\nNAS\n80\n\n1\n\n");          /* Not canonical. */
    refuseRecord("GHServer1\nhttp\nnas\n080\n\n1\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n0\n\n1\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n70000\n\n1\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n80\nnoslash\n1\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n80\n/a/../b\n1\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n80\n\n2\n\n");
    refuseRecord("GHServer1\nhttp\nnas\n80\n\n1\nuser:pass\n");
    refuseRecord("GHServer1\nhttp\nna s\n80\n\n1\n\n");
    CHECK(GRUnpack((const unsigned char *)"GHServer1\nhttp\nnas\n80\n\n1\n\0\n",25,&s)==GB_BAD);

    printf("Server addresses: %u checks passed\n",checks);
    return 0;
}
