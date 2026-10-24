"""Fail closed on broken HFS B-tree indexes and leaf chains before extraction.

Input is an immutable, already detached image byte string. No repair, silent
record skipping, or partial extraction. This checks index/leaf structure/counts;
it is not a complete HFS allocation/index/volume consistency checker.
"""
import struct
from machfs import btree
import machfs

def leaves(buf):
    def node(number):
        if number<0 or number*512+512>len(buf):raise ValueError('HFS node outside fork')
        at=number*512
        forward,back,kind,height,count=struct.unpack_from('>LLBBH',buf,at)
        if count>248:raise ValueError('Invalid HFS node record count')
        offsets=list(reversed(struct.unpack_from('>'+str(count+1)+'H',buf,at+512-2*(count+1))))
        if offsets[0]<14 or offsets[-1]>512-2*(count+1) or any(a>=b for a,b in zip(offsets,offsets[1:])):
            raise ValueError('Invalid HFS record offsets')
        return forward,back,kind,height,[buf[at+a:at+b] for a,b in zip(offsets,offsets[1:])]
    _,_,kind,_,records=node(0)
    if kind!=1 or len(records)!=3 or len(records[0])<30:raise ValueError('Invalid HFS B-tree header')
    depth,root,count,first,last,size,key,nodes,free=struct.unpack_from('>HLLLLHHLL',records[0])
    if size!=512 or nodes*512>len(buf) or free>nodes:raise ValueError('Invalid HFS B-tree geometry')
    if not depth:
        if root or count or first or last:raise ValueError('Invalid empty HFS B-tree')
        return iter(())
    if not root or not first or not last or root>=nodes:raise ValueError('Invalid HFS B-tree root/leaves')
    # A readable leaf chain does not prove that File Manager can find its rows.
    # Validate index children as well as the linked leaf chain.
    indexed=[];visited=set()
    def walk(number,expected):
        if number in visited or not 0<number<nodes:raise ValueError('Repeated/out-of-range HFS index child')
        visited.add(number)
        _,_,kind,height,rows=node(number)
        if height!=expected or kind!=(255 if expected==1 else 0) or not rows:
            raise ValueError('Invalid HFS index child kind/height')
        if expected==1:
            indexed.append(number)
        else:
            for row in rows:
                at=(row[0]+2)&~1
                if at+4>len(row):raise ValueError('Truncated HFS index pointer')
                walk(struct.unpack_from('>L',row,at)[0],expected-1)
    walk(root,depth)
    seen=set();seenOrder=[];current=first;previous=0;total=0;accepted=[]
    while True:
        if current in seen or not 0<current<nodes:raise ValueError('Cyclic/out-of-range HFS leaf chain')
        seen.add(current)
        seenOrder.append(current)
        forward,back,kind,height,rows=node(current)
        if kind!=255 or height!=1 or back!=previous:raise ValueError('Invalid HFS leaf descriptor/backlink')
        total+=len(rows)
        if total>count:raise ValueError('HFS leaf record total exceeds header')
        accepted.extend(rows)
        if current==last:
            if forward or total!=count:raise ValueError('HFS leaf terminus/count mismatch')
            if indexed!=seenOrder:raise ValueError('HFS index and leaf chain disagree')
            return iter(accepted)
        previous,current=current,forward

def volume(image):
    old=btree.dump_btree
    btree.dump_btree=leaves
    try:
        result=machfs.Volume();result.read(image)
        return result
    finally:btree.dump_btree=old


from machfs.main import _get_every_extent

def catalog(image):
    assert image[1024:1026]==b'BD', 'Expected an unpartitioned HFS test image'
    m=struct.unpack_from('>2sLLHHHHHLLHLH28pLHLLLHLL32sHHHL12sL12s',image,1024)
    block_size,start=m[8],m[10]*512
    overflow={}
    def fork(size,extents,cnid,kind):
        spans=_get_every_extent((size+block_size-1)//block_size,extents,cnid,overflow,kind)
        return b''.join(image[start+a*block_size:start+(a+b)*block_size] for a,b in spans)[:size]
    for rec in leaves(fork(m[26],m[27],3,'data')):
        if rec[0]!=7:
            continue
        kind,cnid,logical,extents=struct.unpack_from('>xBLH12s',rec)
        assert kind in (0,255)
        overflow[cnid,'rsrc' if kind else 'data',logical]=extents
    records={}
    for rec in leaves(fork(m[28],m[29],4,'data')):
        key_length=rec[0]
        if not key_length:
            continue
        key=rec[2:1+key_length]
        parent,n=struct.unpack_from('>LB',key)
        name=key[5:5+n]
        val=rec[(key_length+2)&~1:]
        if val[0]==1:
            flags,children,cnid,created,modified,backup,info,extended=struct.unpack_from('>HHLLLL16s16s',val,2)
            record=dict(kind=2,id=cnid,parent=parent,name=name,created=created,modified=modified,
                        backup=backup,children=children,data_length=0,resource_length=0,
                        info=info+extended,locked=flags&1)
        elif val[0]==2:
            fields=struct.unpack_from('>BB16sLHLLHLLLLL16sH12s12sxxxx',val,2)
            flags,_,info,cnid,_,dn,_,_,rn,_,created,modified,backup,extended,_,_,_=fields
            record=dict(kind=1,id=cnid,parent=parent,name=name,created=created,modified=modified,
                        backup=backup,children=0,data_length=dn,resource_length=rn,
                        info=info+extended,locked=flags&1)
        else:
            continue
        assert cnid not in records
        records[cnid]=record
    def components(cnid):
        parts=[]
        seen=set()
        while cnid!=2:
            assert cnid not in seen
            seen.add(cnid)
            record=records[cnid]
            parts.append(record['name'])
            cnid=record['parent']
        return tuple(reversed(parts))
    return {components(i):r for i,r in records.items()}

