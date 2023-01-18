import os
import pathlib
import shutil
from typing import List, Optional

import awkward as ak
import pandas as pd


def ak_to_pandas(self, jet_collection: ak.Array) -> pd.DataFrame:
    out_df = pd.DataFrame()
    for field in ak.fields(jet_collection):
        prefix = self.prefixes.get(field, "")
        if len(prefix) > 0:
            for subfield in ak.fields(jet_collection[field]):
                out_df[f"{prefix}_{subfield}"] = ak.to_numpy(
                    jet_collection[field][subfield]
                )
        else:
            out_df[field] = ak.to_numpy(jet_collection[field])
    return out_df


def h5store(
    self, store: pd.HDFStore, df: pd.DataFrame, fname: str, gname: str, **kwargs: float
) -> None:
    store.put(gname, df)
    store.get_storer(gname).attrs.metadata = kwargs


def save_dfs(self, dfs, df_names, fname):
    # fname = "out.hdf5"
    subdirs = []
    store = pd.HDFStore(fname)
    if self.output_location is not None:
        # pandas to hdf5
        for out, gname in zip(dfs, df_names):
            if self.isMC:
                metadata = dict(
                    gensumweight=self.gensumweight,
                    era=self.era,
                    mc=self.isMC,
                    sample=self.sample,
                )
                # metadata.update({gensumweight:self.gensumweight})
            else:
                metadata = dict(era=self.era, mc=self.isMC, sample=self.sample)

            h5store(self, store, out, fname, gname, **metadata)

        store.close()
        dump_table(self, fname, self.output_location, subdirs)
    else:
        print("self.output_location is None")
        store.close()


def dump_table(
    self, fname: str, location: str, subdirs: Optional[List[str]] = None
) -> None:
    subdirs = subdirs or []
    xrd_prefix = "root://"
    pfx_len = len(xrd_prefix)
    xrootd = False
    if xrd_prefix in location:
        try:
            import XRootD
            import XRootD.client

            xrootd = True
        except ImportError as exc:
            raise ImportError(
                "Install XRootD python bindings with: conda install -c conda-forge xroot"
            ) from exc
    local_file = (
        os.path.abspath(os.path.join(".", fname))
        if xrootd
        else os.path.join(".", fname)
    )
    merged_subdirs = "/".join(subdirs) if xrootd else os.path.sep.join(subdirs)
    destination = (
        location + merged_subdirs + f"/{fname}"
        if xrootd
        else os.path.join(location, os.path.join(merged_subdirs, fname))
    )
    if xrootd:
        copyproc = XRootD.client.CopyProcess()
        copyproc.add_job(local_file, destination)
        copyproc.prepare()
        copyproc.run()
        client = XRootD.client.FileSystem(
            location[: location[pfx_len:].find("/") + pfx_len]
        )
        status = client.locate(
            destination[destination[pfx_len:].find("/") + pfx_len + 1 :],
            XRootD.client.flags.OpenFlags.READ,
        )
        assert status[0].ok
        del client
        del copyproc
    else:
        dirname = os.path.dirname(destination)
        if not os.path.exists(dirname):
            pathlib.Path(dirname).mkdir(parents=True, exist_ok=True)
        if not os.path.samefile(local_file, destination):
            shutil.copy2(local_file, destination)
        else:
            fname = "condor_" + fname
            destination = os.path.join(location, os.path.join(merged_subdirs, fname))
            shutil.copy2(local_file, destination)
        assert os.path.isfile(destination)
    pathlib.Path(local_file).unlink()
