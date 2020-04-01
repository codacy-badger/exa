# Copyright (c) 2015-2020, Exa Analytics Development Team
# Distributed under the terms of the Apache License 2.0
"""
Data
########
"""
import yaml
import importlib
from copy import deepcopy
from pathlib import Path

from traitlets import List, Unicode, Dict, Any, Tuple
from traitlets import validate, default, observe
from traitlets import TraitError
import pandas as pd

import exa
from exa.core.error import RequiredColumnError


class Data(exa.Base):
    """An interface to separate data provider routing
    logic and simplify managing multiple data concepts
    in the container.
    """
    name = Unicode(help="string name of data")
    meta = Dict(help="metadata dictionary")
    source = Any(allow_none=True, help="a callable that takes priority over a __call__ method")
    call_args = List(help="args to pass to call or source")
    call_kws = Dict(help="kwargs to pass to call or source")
    index = Unicode(help="index name") # is this required for Container.network?
    # cardinal can maybe just be indexes (or indexes[0]?)
    cardinal = Unicode(help="cardinal slicing field")
    # TODO : cardinal, index, indexes are related..
    indexes = List(help="columns that guarantee uniqueness")
    columns = List(help="columns that must be present in the dataset")
    # generalize to dtypes?
    categories = Dict()

    def slice(self, key):
        """Provide a programmatic way to slice contained
        data without operating on the dataframe directly.
        """

    def groupby(self, columns=None):
        """Convenience method for pandas groupby"""
        cols = columns or self.indexes
        df = self.data()
        if isinstance(df, pd.DataFrame):
            if cols:
                return df.groupby(cols)
            self.log.warning("no columns to group by")
        self.log.warning("no dataframe to group by")

    def memory(self):
        """Return the memory footprint of the underlying
        data stored in Data"""
        mem = 0
        df = self.data()
        if isinstance(df, pd.DataFrame):
            mem = df.memory_usage()
        return mem

    def __call__(self, *args, **kws):
        self.log.warning("call not implemented")

    @validate('source')
    def _validate_source(self, prop):
        """source must implement __call__. If specified
        as a namespace path in a config, it must be a
        function. If provided dynamically, any callable
        will do."""
        source = prop['value']
        self.log.debug(f"validating {source}")
        if isinstance(source, str):
            # Assume source is a namespace to a callable
            try:
                *mod, obj = source.split('.')
                mod = importlib.import_module('.'.join(mod))
                source = getattr(mod, obj)
            except Exception as e:
                self.log.error(f"could not import {obj} from {mod}")
                raise TraitError("source must be importable")
        if not callable(source):
            raise TraitError("source must be callable")
        return source

    @observe('source')
    def _observe_source(self, change):
        """Update stored data if source changes. Nullify
        related traits when source is nullified to reset
        state of the Data object."""
        if change.new is None:
            self._data = None
            self.call_args = []
            self.call_kws = {}

    @validate('name')
    def _validate_name(self, prop):
        name = prop['value']
        self.log.debug(f"lowercasing {name}")
        return name.lower()

    @default('name')
    def _default_name(self):
        return self.__class__.__name__

    @validate('cardinal')
    def _validate_cardinal(self, prop):
        c = prop['value']
        if self.indexes and c not in self.indexes:
            raise TraitError(f"{c} not in {self.indexes}")
        return c

    def copy(self, *args, **kws):
        """All args and kwargs are forwarded to
        data().copy method and assumes a deepcopy
        of the Data object itself."""
        cls = self.__class__
        if hasattr(self.data(), 'copy'):
            return cls(data=self.data().copy(*args, **kws),
                       **deepcopy(self.trait_items()))
        return cls(data=deepcopy(self.data()),
                   **deepcopy(self.trait_items()))

    def data(self, df=None, cache=True):
        """Return the currently stored data in the
        Data object. If df is provided, store that
        as the current data and return it. Otherwise,
        determine the source to call to obtain
        the data, store it and return it.

        Note:
            behaves like a setter if df is provided

        Note:
            force re-evaluation of source if cache is False
        """
        _data = getattr(self, '_data', None)
        if not cache:
            _data = None
        if df is not None:
            _data = df
        if _data is None:
            f = self.source or self.__call__
            _data = f(*self.call_args, **self.call_kws)
        self._data = self._validate_data(_data)
        return self._data

    def _validate_data(self, df, reverse=False):
        if not isinstance(df, pd.DataFrame):
            self.log.warning("data not a dataframe, skipping validation")
            return df
        if self.index and df.index.name != self.index:
            self.log.debug("setting index name {}".format(self.index))
            df.index.name = self.index
        missing = set(self.columns).difference(df.columns)
        if missing:
            raise RequiredColumnError(missing, self.name)
        df = self._set_categories(df, reverse=reverse)
        if self.indexes and df.duplicated(subset=self.indexes).any():
            raise TraitError(f"duplicates in {self.indexes}")
        return df

    def load(self, name=None, directory=None):
        """Load a saved Data from its stored metadata yaml
        and parquet data file."""
        name = name or self.name
        directory = Path(directory) or exa.cfg.savedir
        self.log.info(f"loading {directory / name}")
        if (directory / f'{name}.yml').exists():
            yml = self._from_yml(directory / f'{name}.yml')
            for attr, vals in yml.items():
                setattr(self, attr, vals)
        if (directory / f'{name}.qet').exists():
            self._data = pd.read_parquet(
                directory / f'{name}.qet', columns=self.columns
            )

    def save(self, name=None, directory=None):
        """Save the housed dataframe as a parquet file and related
        metadata as a yml file with the same name."""
        name = name or self.name
        directory = Path(directory) or exa.cfg.savedir
        directory.mkdir(parents=True, exist_ok=True)
        data = self.data()
        if isinstance(data, pd.DataFrame):
            data.to_parquet(directory / f'{name}.qet')
            self._data = None
        save = self.trait_items()
        source = save.pop('source', None)
        if source is not None:
            save['source'] = '.'.join((source.__module__, source.__name__))
        with open(directory / f'{name}.yml', 'w') as f:
            yaml.dump(save, f, default_flow_style=False)
        if data is not None:
            self.data(df=data)

    def _set_categories(self, df, reverse=False):
        """For specified categorical fields,
        convert to pd.Categoricals.

        Note:
            If reverse is True, revert categories
        """
        for col, typ in self.categories.items():
            conv = {True: typ, False: 'category'}[reverse]
            if col in df.columns:
                df[col] = df[col].astype(conv)
            else:
                self.log.debug(
                    f"categorical {col} specified but not in data"
                )
        return df

    def __init__(self, *args, data=None, **kws):
        super().__init__(*args, **kws)
        # setting source invalidates _data so do it after
        if data is not None:
            self.data(df=data)


def load_isotopes():
    """Minimal working example of a pluggable
    callable to serve as a data provider in the
    Data API.
    """
    path = exa.cfg.resource('isotopes.json')
    df = pd.read_json(path, orient='values')
    df.columns = ('A', 'Z', 'af', 'afu',
                  'cov_radius', 'van_radius', 'g',
                  'mass', 'massu', 'name', 'eneg',
                  'quad', 'spin', 'symbol', 'color')
    # this sorting is to facilitate comparison
    # with the original implementation.
    return df.sort_values(by=['symbol', 'A']).reset_index(drop=True)

def load_constants():
    """Following suit until more is decided on
    Editor updates.
    """
    path = exa.cfg.resource('constants.json')
    return pd.read_json(path, orient='values')

def load_units():
    """Same. Move these loaders somewhere else."""
    path = exa.cfg.resource('units.json')
    return pd.read_json(path) #, orient='values')

Isotopes = Data(source=load_isotopes, name='isotopes')
Constants = Data(source=load_constants, name='constants')
Units = Data(source=load_units, name='units')


class Field(Data):
    field_values = List()
