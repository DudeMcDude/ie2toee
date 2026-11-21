from templeplus.pymod import PythonModifier
from templeplus.constants import ET_OnD20PythonQuery


def dies_at_zero_hp(attachee, args, evt_obj):
    evt_obj.return_val = 1
    return 0


raider = PythonModifier("IE Siege Raider", 0)
raider.AddHook(ET_OnD20PythonQuery, "Dies at Zero HP", dies_at_zero_hp, ())
