#because prctl-python needed libcap for whatever reason
import ctypes

_reaper_dll = ctypes.cdll.LoadLibrary('./libreaper.so')
set_pdeathsig = _reaper_dll.set_pdeathsig
