"""
monobit.fzx - FZX format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from itertools import accumulate

from ..binary import ceildiv
from ..struct import Props, bitfield, little_endian as le
from ..storage import loaders, savers
from ..font import Font
from ..glyph import Glyph
from ..label import Codepoint
from ..streams import FileFormatError


# beyond ASCII, multiple encodings are in use - set these manually after extraction
_FZX_ENCODING = 'zx-spectrum'
_FZX_RANGE = range(32, 256)


@loaders.register('fzx', name='FZX')
def load_fzx(instream, where=None):
    """Load font from ZX Spectrum .FZX file."""
    fzx_props, fzx_glyphs = _read_fzx(instream)
    logging.info('FZX properties:')
    for line in str(fzx_props).splitlines():
        logging.info('    ' + line)
    props, glyphs = _convert_from_fzx(fzx_props, fzx_glyphs)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    return Font(glyphs, properties=vars(props))


@savers.register(linked=load_fzx)
def save_fzx(fonts, outstream, where=None):
    """Save font to ZX Spectrum .FZX file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to PSF file.')
    font, = fonts
    fzx_props, fzx_glyphs = _convert_to_fzx(font)
    logging.info('FZX properties:')
    for line in str(fzx_props).splitlines():
        logging.info('    ' + line)
    _write_fzx(outstream, fzx_props, fzx_glyphs)


###################################################################################################
# FZX binary format

# overview at
# https://faqwiki.zxnet.co.uk/wiki/FZX_format

# more detail in `fzx.txt` in the FZX_Standard distribution
# https://spectrumcomputing.co.uk/index.php?cat=96&id=28171
# https://spectrumcomputing.co.uk/zxdb/sinclair/entries/0028171/FZX_Standard.zip
#
# > The format consists of a three byte header followed by a variable-length table
# > and a variable-length set of character definitions.
# >
# > The header format is:
# >
# > height   - vertical gap between baselines in pixels
# >            This is the number of pixels to move down after a carriage return.
# >
# > tracking - horizontal gap between characters in pixels
# >            Character definitions should not include any white space and this
# >            value should normally be a positive number. It may be zero for
# >            script style fonts where characters run together.
# >
# > lastchar - the ASCII code of the last definition in the font
# >            All characters up to and including this character must have an
# >            entry in the list of definitions although the entry can be blank.
# >
# > The table consists of a three byte entry for each character from ASCII 32 to the
# > last character defined (lastchar), followed by a final word containing the
# > offset to the byte after the last byte of the last definition).
# >
# > The table entry format is:
# >
# > offset   - word containing the offset to the character definition
# >            This is calculated from the start of the table and stored as an
# >            offset rather than an absolute address to make the font relocatable.
# >
# > kern     - a small value (0-3) stored in the highest 2 bits of the offset, that
# >            indicates a certain character must be always moved left by the
# >            specified number of pixels, thus reducing its distance from the
# >            preceding character. In practice this works as a simplified but very
# >            efficient "kerning".
# >
# > shift    - nibble containing the amount of leading for the character (0-15)
# >            This is the number of vertical pixels to skip before drawing the
# >            character. When more than 15 pixels of white space are required the
# >            additional white space must be added to the character definition.
# >
# > width    - nibble containing the width of the character (1-16)
# >            The width of the character definition in pixels. The value stores is
# >            one less than the required value.
# >
# > The word (2 bytes) containing the offset and shift can be calculated as follows:
# >
# >    offset+16384*kern
# >
# > The byte containing the leading and width can be calculated as follows:
# >
# >    16*shift+width-1
# >
# > The character definitions consist of a byte or pair of bytes for each row of the
# > character, depending on whether the character is 1 to 8 pixels wide (byte), or
# > 9 to 16 pixels wide (pair of bytes).

_FZX_HEADER = le.Struct(
    height='uint8',
    tracking='int8',
    lastchar='uint8',
)

_CHAR_ENTRY = le.Struct(
    # kern, shift are the high byte
    # but in ctypes, little endian ordering also seems to hold for bit fields
    offset=bitfield('uint16', 14),
    kern=bitfield('uint16', 2),
    # this is actually width-1
    width=bitfield('uint8', 4),
    shift=bitfield('uint8', 4),
)

def _read_fzx(instream):
    """Read FZX binary file and return as properties."""
    data = instream.read()
    header = _FZX_HEADER.from_bytes(data)
    n_chars = header.lastchar - 32 + 1
    # read glyph table
    char_table = _CHAR_ENTRY.array(n_chars).from_bytes(data, _FZX_HEADER.size)
    # > Notice that offsets are not relative to the beginning of the FZX, but relative
    # > to the current position. These offsets determine both image location and size
    # > for each char.
    offsets = [
        _FZX_HEADER.size + _CHAR_ENTRY.size * _i + _entry.offset
        for _i, _entry in enumerate(char_table)
    ] + [None]
    glyph_bytes = [
        data[_offs:_next]
        for _offs, _next in zip(offsets[:-1], offsets[1:])
    ]
    # construct glyphs
    glyphs = [
        Glyph.from_bytes(_glyph, _entry.width+1)
        for _glyph, _entry in zip(glyph_bytes, char_table)
    ]
    # set glyph fzx properties
    glyphs = [
        _glyph.modify(kern=_entry.kern, fzx_width=_entry.width, shift=_entry.shift)
        for _glyph, _entry in zip(glyphs, char_table)
    ]
    return Props(**vars(header)), glyphs


def _write_fzx(outstream, fzx_props, fzx_glyphs):
    """Write FZX properties and glyphs to binary file."""
    header = _FZX_HEADER(
        height=fzx_props.height,
        tracking=fzx_props.tracking,
        lastchar=fzx_props.lastchar,
    )
    n_chars = header.lastchar - 32 + 1
    # construct glyph table
    glyph_bytes = tuple(_glyph.as_bytes() for _glyph in fzx_glyphs)
    # absolute offsets from start of glyph table
    abs_offsets = [0] + list(accumulate(len(_bytes) for _bytes in glyph_bytes))
    # offsets relative to entry
    # 2 extra bytes for the final word between char table and bitmaps
    offsets = (
        _ofs + _CHAR_ENTRY.size * (n_chars - _i) + 2
        for _i, _ofs in enumerate(abs_offsets)
    )
    char_table = _CHAR_ENTRY.array(n_chars)(*(
        _CHAR_ENTRY(
            offset=_offset,
            kern=_glyph.kern,
            width=_glyph.fzx_width,
            shift=_glyph.shift
        )
        for _i, (_glyph, _offset) in enumerate(zip(fzx_glyphs, offsets))
    ))
    # final word containing the offset to the byte after the last byte of the last definition
    final_word = le.uint16(abs_offsets[-1] + 2)
    # write out
    outstream.write(b''.join((
        bytes(header),
        bytes(char_table),
        bytes(final_word),
        *glyph_bytes
    )))


###################################################################################################
# metrics conversion

def _convert_from_fzx(fzx_props, fzx_glyphs):
    """Convert FZX properties and glyphs to standard."""
    # set glyph properties
    glyphs = tuple(
        _glyph.modify(
            codepoint=(_codepoint,),
            offset=(-_glyph.kern, fzx_props.height-_glyph.height-_glyph.shift),
            # +1 because _entry.width is actually width-1
            tracking=(_glyph.fzx_width+1)-_glyph.width
        ).drop_properties(
            'kern', 'fzx_width', 'shift'
        )
        for _codepoint, _glyph in enumerate(fzx_glyphs, start=32)
        # drop undefined glyphs (zero advance empty)
        if (_glyph.width and _glyph.height) or (_glyph.fzx_width+1 + _glyph.tracking - _glyph.kern != 0)
    )
    # set font properties
    # if there are common blank rows, call them leading instead of ascent
    leading = min(_glyph.shift for _glyph in fzx_glyphs)
    properties = Props(
        leading=leading,
        # we don't know ascent & descent but we can't set line-height directly
        ascent=fzx_props.height-leading,
        descent=0,
        tracking=fzx_props.tracking,
        encoding=_FZX_ENCODING,
    )
    return properties, glyphs


def _convert_to_fzx(font):
    """Convert monobit font to FZX properties and glyphs."""
    # select glyphs that can be included
    # only codepoints 32--255 inclusive
    # on extraction 32--127 will be assumed to be ASCII
    includable = font.subset(codepoints=set(_FZX_RANGE))
    dropped = font.without(codepoints=set(_FZX_RANGE))
    if dropped.glyphs:
        logging.warning(
            'FZX format can only store codepoints 32--255. '
            'Not all glyphs in this font can be included.'
        )
    # get contiguous range, fill gaps with empties
    glyphs = tuple(
        includable.get_glyph(codepoint=_cp, missing='empty').modify(codepoint=_cp)
        for _cp in _FZX_RANGE
    )
    # remove empties at end
    while not glyphs[-1].width:
        glyphs = glyphs[:-1]
    # TODO: bring on normal form first
    common_tracking = min(_glyph.tracking for _glyph in glyphs)
    # set glyph FZX properties
    fzx_glyphs = tuple(
        # make zero-width glyphs into 1-width glyphs with 1 step back as we can't store zero width
        Glyph(kern=1, shift=font.line_height, fzx_width=0)
        if not _glyph.width else
        _glyph.modify(
            offset=(),
            tracking=0,
            kern=-_glyph.offset.x,
            # line height includes leading
            shift=font.line_height-_glyph.offset.y-_glyph.height,
            # absorb per-glyph tracking by extending fzx width
            fzx_width=_glyph.width + _glyph.tracking - common_tracking - 1,
        )
        for _glyph in glyphs
    )
    # check glyph dimensions / bitfield ranges
    if not glyphs:
        raise FileFormatError('FZX format: no glyphs in storable codepoint range 32--255.')
    if any(_glyph.fzx_width < 0 or _glyph.fzx_width > 15 for _glyph in fzx_glyphs):
        raise FileFormatError('FZX format: glyphs must be from 1 to 16 pixels wide.')
    if any(_glyph.kern < 0 or _glyph.kern > 3 for _glyph in fzx_glyphs):
        raise FileFormatError('FZX format: glyph offset must be in range -3--0.')
    if any(_glyph.shift > 15 for _glyph in fzx_glyphs):
        # TODO: resize character to reduce shift
        raise FileFormatError('FZX format: distance between raster top and line height must be in range 0--15.')
    tracking = font.tracking + common_tracking
    if tracking < -128 or tracking > 127:
        raise FileFormatError('FZX format: tracking must be in range -128--127.')
    # set font FZX properties
    fzx_props = Props(
        tracking=tracking,
        height=font.line_height,
        lastchar=len(glyphs) + min(_FZX_RANGE) - 1
    )
    return fzx_props, fzx_glyphs
