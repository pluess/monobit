"""
monobit.formats - loader and saver plugin registry

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import io
import sys
import gzip
import logging
from functools import wraps
from pathlib import Path

from .base import VERSION, DEFAULT_FORMAT, scriptable
from .containers import open_container, unique_name, containers
from .font import Font
from .pack import Pack
from . import streams
from .streams import compressors, has_magic


# identify font file format from suffix

def get_format(file, format=''):
    """Get format name from file name."""
    if not format:
        format = DEFAULT_FORMAT
        # if filename given, try to use it to infer format
        name = streams.get_stream_name(file)
        suffixes = Path(name).suffixes
        if suffixes:
            # container/compressed formats often have names like .format.gz
            if len(suffixes) >= 2 and (
                    containers.has_suffix(suffixes[-1])
                    or compressors.has_suffix(suffixes[-1])
                ):
                format = suffixes[-2]
            else:
                format = suffixes[-1]
    # normalise suffix
    if format.startswith('.'):
        format = format[1:]
    return format.lower()


##############################################################################
# loading

class Loaders:
    """Loader plugin registry."""

    _loaders = {}
    _magic = {}

    @classmethod
    def get_loader(cls, infile, format=''):
        """Get loader function for this format."""
        # try to use magic sequences
        if infile:
            if isinstance(infile, (str, bytes, Path)):
                try:
                    with streams.open_stream(infile, 'r', binary=True) as stream:
                        return cls.get_loader(stream, format)
                except IsADirectoryError:
                    pass
            else:
                if infile.readable():
                    for magic, loader in cls._magic.items():
                        if has_magic(infile, magic):
                            return loader
        format = get_format(infile, format)
        try:
            return cls._loaders[format]
        except KeyError:
            raise ValueError('Cannot load from format `{}`'.format(format)) from None

    @classmethod
    def load(cls, infile:str, format:str='', **kwargs):
        """Read new font from file."""
        loader = cls.get_loader(infile, format)
        return loader(infile, **kwargs)

    @classmethod
    def register(cls, *formats, magic=(), name=None, binary=False, multi=False, container=False):
        """
        Decorator to register font loader.
            *formats: list of extensions covered by this function
            name: name of the format
            binary: format is binary, not text
            multi: format can contain multiple fonts
            container: format is stored as files in a directory or other container
        """
        if name is None:
            name = formats[0]

        def _load_decorator(load):

            # stream input wrapper
            @wraps(load)
            def _load_func(infile, **kwargs):
                if container:
                    return _load_container_format(load, infile, binary, multi, name, **kwargs)
                try:
                    return _load_streams_from_container(load, infile, binary, multi, name, **kwargs)
                except TypeError:
                    return _load_stream_format(load, infile, binary, multi, name, **kwargs)

            # register loader
            _load_func.script_args = load.__annotations__
            for format in formats:
                cls._loaders[format.lower()] = _load_func
            for sequence in magic:
                cls._magic[sequence] = _load_func
            return _load_func

        return _load_decorator


def _load_container_format(load, infile, binary, multi, format, **kwargs):
    """Open a container and provide to font loader."""
    with open_container(infile, 'r') as zip_con:
        font_or_pack = load(zip_con, **kwargs)
        return _set_extraction_props(font_or_pack, infile, format)

def _load_stream_format(load, infile, binary, multi, format, **kwargs):
    """Load font or pack from stream."""
    with streams.open_stream(infile, 'r', binary) as instream:
        # Stream object always has a .name
        name = Path(instream.name).name
        font_or_pack = load(instream, **kwargs)
    return _set_extraction_props(font_or_pack, name, format)

def _load_streams_from_container(load, infile, binary, multi, format, **kwargs):
    """Open container and load all fonts found in it into one pack."""
    # try opening a container, will raise error if not container format
    with open_container(infile, 'r') as zip_con:
        packs = []
        for name in zip_con:
            with streams.open_stream(name, 'r', binary, on=zip_con) as stream:
                font_or_pack = load(stream, **kwargs)
            font_or_pack = _set_extraction_props(font_or_pack, name, format)
            if isinstance(font_or_pack, Pack):
                packs.append(font_or_pack)
            else:
                packs.append([font_or_pack])
        # flatten list of packs
        fonts = [_font for _pack in packs for _font in _pack]
        return Pack(fonts)


# extraction properties

def _set_extraction_props(font_or_pack, name, format):
    """Return copy with source-name and source-format set."""
    if isinstance(font_or_pack, Pack):
        return Pack(
            _set_extraction_props(_font, name, format)
            for _font in font_or_pack
        )
    font = font_or_pack
    new_props = {
        'converter': 'monobit v{}'.format(VERSION),
        'source-format': font.source_format or format,
        'source-name': font.source_name or name
    }
    return font.set_properties(**new_props)



##############################################################################
# saving

class Savers:
    """Saver plugin registry."""

    _savers = {}

    @classmethod
    def get_saver(cls, outfile, format=''):
        """Get saver function for this format."""
        format = get_format(outfile, format)
        try:
            return cls._savers[format]
        except KeyError:
            raise ValueError('Cannot save to format `{}`'.format(format))

    @classmethod
    def save(cls, pack, outfile:str, format:str='', **kwargs):
        """Write to file, return unchanged."""
        saver = cls.get_saver(outfile, format)
        saver(pack, outfile, **kwargs)
        return pack

    @classmethod
    def register(cls, *formats, binary=False, multi=False, container=False):
        """
        Decorator to register font saver.
            *formats: extensions covered by registered function
            binary: format is binary, not text
            multi: format can contain multiple fonts
            container: format is stored as files in a directory or other container
        """

        def _save_decorator(save):
            # stream output wrapper
            @wraps(save)
            def _save_func(pack_or_font, outfile, **kwargs):
                if isinstance(pack_or_font, Font):
                    pack = Pack([pack_or_font])
                else:
                    pack = pack_or_font
                if container:
                    _save_container_format(save, pack, outfile, **kwargs)
                elif multi:
                    _save_stream_format(save, pack, outfile, binary, **kwargs)
                else:
                    # use first extension provided by saver function
                    _save_streams(save, pack, outfile, binary, formats[0], **kwargs)

            # register saver
            _save_func.script_args = save.__annotations__
            for format in formats:
                cls._savers[format.lower()] = _save_func
            return _save_func

        return _save_decorator


def _save_container_format(save, pack, outfile, **kwargs):
    """Call a pack or font saving function, save to a container."""
    with open_container(outfile, 'w') as out:
        save(pack, out, **kwargs)

def _save_stream_format(save, pack, outfile, binary, **kwargs):
    """Call a pack saving function, save to a stream."""
    with streams.open_stream(outfile, 'w', binary) as outstream:
        save(pack, outstream, **kwargs)

def _save_streams(save, pack, outfile, binary, ext, **kwargs):
    """Call a font saving function, save to a stream or container."""
    if len(pack) == 1:
        # we have only one font to deal with, no need to create container
        _save_stream_format(save, [*pack][0], outfile, binary, **kwargs)
    else:
        # create container and call saver for each font in the pack
        with open_container(outfile, 'w', binary) as out:
            # save fonts one-by-one
            for font in pack:
                # generate unique filename
                name = font.name.replace(' ', '_')
                filename = unique_name(out, name, ext)
                try:
                    with streams.open_stream(filename, 'w', binary, on=out) as stream:
                        save(font, stream, **kwargs)
                except BrokenPipeError:
                    pass
                except Exception as e:
                    logging.error('Could not save %s: %s', filename, e)
                    raise
