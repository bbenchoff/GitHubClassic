#!/usr/bin/env python3
"""Create detached, disposable GH Merge HFS media for the native diagnostic.

Requires Git and machfs 1.3. Never attaches media or opens a working Mac disk.
Existing output files are refused. Each application slice gets fresh fixtures.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
import zlib

import machfs
from mac_forks import VERSION


@dataclass(frozen=True)
class File:
    data: bytes
    info: bytes | None = None
    resource: bytes = b""
    mode: int = 0o100644


def metadata(name, value):
    apple = (struct.pack(">II16sH", 0x51607, 0x20000, bytes(16), 2)
             + struct.pack(">III", 9, 50, 32)
             + struct.pack(">III", 2, 82, len(value.resource))
             + value.info + value.resource)
    return b"GHMETA01" + struct.pack(">I", len(name)) + name + apple


def file(data=b"", kind=b"BINA", creator=b"GHCl", resource=b""):
    result = machfs.File()
    result.data, result.type, result.creator, result.rsrc = data, kind, creator, resource
    result.crdate = result.mddate = 1792018800 + 2082844800
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new detached .hfs image")
    options = parser.parse_args()
    report_path = options.output.with_suffix(".json")
    if options.output.exists() or report_path.exists():
        parser.error("keep existing fixture images and result manifests; choose a new output")
    objects={}
    def put(kind,body):
        raw=kind.encode()+b' '+str(len(body)).encode()+b'\0'+body;key=hashlib.sha1(raw).hexdigest();objects[key]=raw;return key
    def entries(files):
        rows=[]
        for name,f in files.items():
            rows.append((name,0o100644 if f.mode is None else f.mode,put('blob',f.data),len(f.data)))
            if f.info is not None:
                key=hashlib.sha1(name).hexdigest();key=f'.ghclient-mac/forks/{key[:2]}/{key[2:14]}/{key[14:]}'.encode()
                raw=metadata(name,f);rows.append((key,0o100644,put('blob',raw),len(raw)))
        if any(f.info is not None for f in files.values()):rows.append((b'.ghclient-mac/version',0o100644,put('blob',VERSION),len(VERSION)))
        return sorted(rows)
    def tree(rows):
        root={}
        for path,mode,oid,n in rows:
            parts=path.split(b'/');at=root
            for part in parts[:-1]:at=at.setdefault(part,{})
            at[parts[-1]]=(mode,oid)
        def emit(at):
            rows=[]
            for name,value in at.items():
                mode,key=(0o40000,emit(value)) if isinstance(value,dict) else value
                rows.append((name+(b'/' if mode==0o40000 else b''),f'{mode:o} '.encode()+name+b'\0'+bytes.fromhex(key)))
            return put('tree',b''.join(raw for name,raw in sorted(rows)))
        return emit(root)
    def index(rows):
        out=b'DIRC'+struct.pack('>II',2,len(rows))
        for path,mode,key,n in rows:
            row=struct.pack('>10I20sH',0,0,0,0,0,0,mode,0,0,n,bytes.fromhex(key),len(path))+path+b'\0'
            out+=row+b'\0'*((-len(row))%8)
        return out+hashlib.sha1(out).digest()
    def commit(files,parents=(),message=b'fixture\n',identity=b'Fixture <fixture@example.invalid>'):
        tid=tree(entries(files))
        body=b'tree '+tid.encode()+b'\n'+b''.join(b'parent '+p.encode()+b'\n' for p in parents)
        body+=b'author '+identity+b' 1792018800 -0700\ncommitter '+identity+b' 1792018800 -0700\n\n'+message
        return put('commit',body),tid
    info=b'TEXTttxt'+bytes(24);changedInfo=b'TEXTCWIE'+bytes(24)
    b={b'Story':File(b'one\nmiddle\nlast\n',info=info,resource=b'R0'),b'Keep':File(b'untouched\r',info=info,resource=b'keep resource')}
    c={**b,b'Story':replace(b[b'Story'],data=b'ours\nmiddle\nlast\n',info=changedInfo,mode=0o100755)}
    o={**b,b'Story':replace(b[b'Story'],data=b'one\nmiddle\nother\n',resource=b'R1')}
    m={**c,b'Story':replace(c[b'Story'],data=b'ours\nmiddle\nother\n',resource=b'R1')}
    root,_=commit(b,message=b'base\n');left,_=commit(c,[root],b'current\n');right,rt=commit(o,[root],b'incoming\n')
    mc={**c,b'Story':replace(c[b'Story'],resource=b'CURRENT')};mo={**o,b'Story':replace(o[b'Story'],resource=b'OTHER')}
    conflictLeft,_=commit(mc,[root],b'conflicting current\n');conflictRight,_=commit(mo,[root],b'conflicting incoming\n')
    inputObjects=dict(objects) # Expected candidate blobs/trees/commits must be created by the app.
    identity=b'GHClient Test <test@example.invalid>'
    merged,mt=commit(m,[left,right],b'Native merge checkout\n',identity)
    forced,_=commit(o,[root,right],b'Native merge checkout\n',identity)
    cases=[('Merge',left,right,c,m,merged,mt,3,0),('Forward',root,right,b,o,right,rt,2,0),
        ('Forced',root,right,b,o,forced,rt,3,0),('Conflict',conflictLeft,conflictRight,mc,mc,conflictLeft,None,4,-30),
        ('Stale',left,right,c,c,left,None,3,-21),('Current',left,root,c,c,left,None,1,0)]
    # Independently import/parse every object and verify tree, message and parent
    # identities with modern Git before placing them on native media.
    with tempfile.TemporaryDirectory(prefix='gh-merge-fixture-') as temporary:
        directory=Path(temporary)
        def git(*args,data=None):return subprocess.run(['git','-C',str(directory),*args],input=data,capture_output=True,check=True).stdout
        git('init','--quiet','--object-format=sha1')
        for key,raw in objects.items():
            header,body=raw.split(b'\0',1);kind,length=header.split();assert int(length)==len(body)
            assert git('hash-object','-w','-t',kind.decode(),'--stdin',data=body).strip().decode()==key
        git('fsck','--full','--strict','--no-dangling')
        ge=dict(os.environ,GIT_AUTHOR_NAME='GHClient Test',GIT_AUTHOR_EMAIL='test@example.invalid',
            GIT_COMMITTER_NAME='GHClient Test',GIT_COMMITTER_EMAIL='test@example.invalid',
            GIT_AUTHOR_DATE='@1792018800 -0700',GIT_COMMITTER_DATE='@1792018800 -0700')
        for tid,parents,key in [(mt,[left,right],merged),(rt,[root,right],forced)]:
            args=['git','-C',str(directory),'commit-tree',tid]
            for parent in parents:args+=['-p',parent]
            assert subprocess.run(args,input=b'Native merge checkout\n',capture_output=True,env=ge,check=True).stdout.strip().decode()==key
    volume = machfs.Volume()
    volume.name = "GH Merge"
    results = []

    def add_bytes(folder, name, raw, kind=b"BINA", creator=b"GHCl", resource=b""):
        parts = name.split("/")
        for part in parts[:-1]:
            if part not in folder:
                folder[part] = machfs.Folder()
            folder = folder[part]
        folder[parts[-1]] = file(raw, kind, creator, resource)

    def add_ref(folder, name, oid):
        digest = hashlib.sha1(name.encode("ascii")).hexdigest()
        add_bytes(folder, "refs/%s/%s/%s" % (digest[:2], digest[2:14], digest[14:]),
                  name.encode("ascii") + b"\0" + oid.encode("ascii") + b"\n")

    for slot in ("PPC", "68K", "FAT"):
        for name, current, other, working, expected_files, after, tree_id, kind, result in cases:
            title = slot + " " + name
            folder = volume[title] = machfs.Folder()
            store = folder[".git"] = machfs.Folder()
            add_bytes(store, "format", b"GHClient repository 1\nobjects sha1-zlib 2/12/26\nrefs sha1-name\n")
            add_bytes(store, "HEAD", b"ref: refs/heads/main\n")
            add_ref(store, "refs/heads/main", current)
            add_ref(store, "refs/remotes/origin/topic", other)
            add_bytes(store, "index", index(entries(working)))
            for oid, raw in inputObjects.items():
                add_bytes(store, "objects/%s/%s/%s" % (oid[:2], oid[2:14], oid[14:]), zlib.compress(raw))
            for logical, value in working.items():
                info = value.info or b"GHCf" + bytes(28)
                add_bytes(folder, logical.decode("ascii"), value.data, info[:4], info[4:8], value.resource)
            volume[title + " Inputs"] = file(b"GHMERGE1" + bytes.fromhex(current + other + root))
            results.append({"folder": title, "slot": slot, "current": current, "incoming": other,
                            "expected_other": root if name == "Stale" else other,
                            "expected_tip": after, "expected_kind": kind,
                            "expected_apply": result, "expected_tree": tree_id,
                            "expected_files": {path.decode("ascii"): {"data": value.data.hex(),
                                "resource": value.resource.hex(), "finder": value.info.hex(),
                                "mode": value.mode} for path, value in expected_files.items()}})
    raw = volume.write(size=16 * 1024 * 1024, desktopdb=False, bootable=False)
    report = {"sha256": hashlib.sha256(raw).hexdigest(), "volume": "GH Merge", "cases": results,
              "input_objects": len(inputObjects), "input_oids": sorted(inputObjects),
              "scope": "Disposable native HFS merge, fast-forward, forced merge, conflict, stale and current fixtures. No origins or authorization."}
    with options.output.open("xb") as output:
        output.write(raw)
    with report_path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print("Created %s: 18 native repositories, %d independently verified input objects" % (options.output, len(inputObjects)))


if __name__ == "__main__":
    main()
