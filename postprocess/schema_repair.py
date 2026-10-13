"""Unambiguous named-field conversions. No numeric/identity/time inference."""
import math

def numeric(v):return type(v) in (int,float) and math.isfinite(v)
def point(v,kind):
 keys=('azimuth','elevation') if kind=='doa' else ('x','y','z')
 if isinstance(v,dict) and set(v)==set(keys) and all(numeric(v[k]) for k in keys):return [v[k] for k in keys]
 return v

def repair(v,task):
 original=v;rules=[]
 if task in {'RANGE','TEXT_RANGE'}:
  if isinstance(v,dict) and len(v)==1:
   key=next(iter(v))
   if key in {'distance','distance_m','range','range_m'} and numeric(v[key]):v=v[key];rules.append('unwrap_named_distance')
  if isinstance(v,list) and len(v)==1 and numeric(v[0]):v=v[0];rules.append('unwrap_single_distance')
 if task in {'DOA','TEXT_DOA','C1_SETLOC','C3_TEXTLOC'}:
  kind='doa' if task in {'DOA','TEXT_DOA'} else 'xyz';dim=2 if kind=='doa' else 3
  converted=point(v,kind)
  if converted!=v:v=converted;rules.append('named_point_to_vector')
  if isinstance(v,list):
   converted=[point(x,kind) for x in v]
   if converted!=v:v=converted;rules.append('named_points_to_vectors')
  if task in {'DOA','C1_SETLOC'} and isinstance(v,list) and len(v)==dim and all(numeric(x) for x in v):v=[v];rules.append('wrap_single_point')
  if task in {'TEXT_DOA','C3_TEXTLOC'} and isinstance(v,list) and len(v)==1 and isinstance(v[0],list) and len(v[0])==dim and all(numeric(x) for x in v[0]):v=v[0];rules.append('unwrap_single_target')
 return v,rules
