"""Blind V3 loader with public, prevalidated spatial-cue ablations."""
import copy
from exhibition_dataset.loader import Dataset as BaseDataset
from .common import rows
from .prompts import render

class Dataset(BaseDataset):
    def load(self,sid,context='full',audio=True,cue_variant=None):
        result=super().load(sid,context,audio)
        if cue_variant is None:return result
        if not hasattr(self,'_cue_variants'):
            self._cue_variants={(r['sample_id'],r['variant_id']):r['query'] for r in rows(self.root/'public/test/spatial_query_variants.jsonl')}
        key=(sid,cue_variant)
        if key not in self._cue_variants:raise ValueError('Cue variant is not unambiguous for this sample')
        sample=self._read('inputs',sid);sample['query']=copy.deepcopy(self._cue_variants[key])
        result.update(query=sample['query'],prompt=render(sample,self.contexts[context]))
        return result
