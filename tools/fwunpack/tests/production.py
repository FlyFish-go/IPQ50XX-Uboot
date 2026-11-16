# SPDX-License-Identifier: GPL-2.0-or-later
"""Load the actual rescue validator with today's limits, without a C copy."""
import ctypes
import importlib.util
from pathlib import Path
import re
import os
import subprocess

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('hostubi',ROOT/'u-boot-2016/test/firmware_rt3000_b_ubi_hosttest.py')
host=importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)

def make_lib(tmp):
    # Reuse the repository harness, then refresh its historical PEB count
    # from the production module. No validator code fork.
    os.environ['TMPDIR']=str(tmp)
    host.make_test_lib(tmp)
    p=Path(tmp)/'ubi_validator.c'
    text='#define SZ_1M (1024U * 1024U)\n'+p.read_text()
    source=(ROOT/'u-boot-2016/failsafe/modules/firmware_rt3000_b.c').read_text()
    for name in ('RT3_FW_MAX_UPLOAD','RT3_FW_MAX_PEB_COUNT'):
        line=re.search(r'^#define\s+'+name+r'\s+(.+)$',source,re.M).group(0)
        text=re.sub(r'^#define\s+'+name+r'\s+.+$',lambda _:line,text,flags=re.M)
    p.write_text(text)
    so=Path(tmp)/'production_validator.so'
    subprocess.run(['gcc','-shared','-fPIC','-O2',str(p),'-o',str(so)],check=True)
    lib=ctypes.CDLL(str(so))
    lib.rt3_host_validate.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_uint),ctypes.POINTER(ctypes.c_uint)]
    lib.rt3_host_validate.restype=ctypes.c_int
    return lib
