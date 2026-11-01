import ctypes as C
from pathlib import Path
class Input(C.Structure):
    _fields_=[('ptr',C.c_void_p),('size',C.c_size_t),('editable',C.c_bool)]
class Output(C.Structure):
    _fields_=[('ptr',C.c_void_p),('size',C.c_size_t)]
dll=C.WinDLL(str(Path(__file__).resolve().parents[1]/'downloads/msdelta.dll'),use_last_error=True)
dll.ApplyDeltaB.argtypes=[C.c_ulonglong,Input,Input,C.POINTER(Output)]
dll.ApplyDeltaB.restype=C.c_bool
dll.DeltaFree.argtypes=[C.c_void_p]
p=Path(__file__).resolve().parents[1]/'downloads/kb3065979/payload'
import xml.etree.ElementTree as E,hashlib
ns={'c':'urn:ContainerIndex'}
files={e.get('id'):e for e in E.parse(p/'_manifest_.cix.xml').findall('c:Files/c:File',ns)}
cache={}
def decode(id):
    if id in cache:return cache[id]
    e=files[id]; delta=e.find('c:Delta',ns); source=delta.find('c:Source',ns)
    if source.get('type')=='RAW':result=(p/source.get('name')).read_bytes()
    else:
        data=(p/source.get('name')).read_bytes();basis=delta.find('c:Basis',ns)
        old=decode(basis.get('file')) if basis is not None else b''
        buf=C.create_string_buffer(data);oldbuf=C.create_string_buffer(old);out=Output()
        assert dll.ApplyDeltaB(0,Input(C.cast(oldbuf,C.c_void_p),len(old),False),Input(C.cast(buf,C.c_void_p),len(data),False),C.byref(out)),C.get_last_error()
        result=C.string_at(out.ptr,out.size);dll.DeltaFree(out.ptr)
    assert hashlib.sha1(result).hexdigest()==e.find('c:Hash',ns).get('value').zfill(40)
    cache[id]=result
    return result
for id,e in files.items():
    if e.get('name').endswith('gdiplus.dll'):
        data=decode(id);out=p/(id+'.dll');out.write_bytes(data); print(out,len(data),hashlib.sha256(data).hexdigest())
