"""
monobit.amiga - Amiga font format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import os
import logging

from ..binary import bytes_to_bits
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font, Coord
from ..glyph import Glyph
from ..struct import Props, flag, bitfield, big_endian as be
from .. import struct


@loaders.register('font', magic=(b'\x0f\0', b'\x0f\2'), name='Amiga Font Contents')
def load_amiga_fc(f, where):
    """Load font from Amiga disk font contents (.FONT) file."""
    fch = _FONT_CONTENTS_HEADER.read_from(f)
    if fch.fch_FileID == _FCH_ID:
        logging.debug('Amiga FCH using FontContents')
    elif fch.fch_FileID == _TFCH_ID:
        logging.debug('Amiga FCH using TFontContents')
    else:
        raise FileFormatError(
            'Not an Amiga Font Contents file: '
            f'incorrect magic bytes 0x{fch.fch_FileID:04X} '
            f'not in (0x{_FCH_ID:04X}, 0x{_TFCH_ID:04X}).'
        )
    contentsarray = _FONT_CONTENTS.array(fch.fch_NumEntries).read_from(f)
    pack = []
    for fc in contentsarray:
        # we'll get ysize, style and flags from the file itself, we just need a path.
        name = fc.fc_FileName.decode(_ENCODING)
        # amiga fs is case insensitive, so we need to loop over listdir and match
        for filename in where:
            if filename.lower() == name.lower():
                pack.append(_load_amiga(where.open(filename, 'r'), where))
    return pack


@loaders.register('amiga', magic=(b'\0\0\x03\xf3',), name='Amiga Font')
def load_amiga(f, where=None):
    """Load font from Amiga disk font file."""
    return _load_amiga(f, where)


###################################################################################################
# AmigaOS font format
#
# developer docs: Graphics Library and Text
# https://wiki.amigaos.net/wiki/Graphics_Library_and_Text
# http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03D2.html
#
# references on binary file format
# http://amiga-dev.wikidot.com/file-format:hunk
# https://archive.org/details/AmigaDOS_Technical_Reference_Manual_1985_Commodore/page/n13/mode/2up (p.14)


# latin-1 seems to be the standard for amiga strings,
# see e.g. https://wiki.amigaos.net/wiki/FTXT_IFF_Formatted_Text#Data_Chunk_CHRS
_ENCODING = 'latin-1'

# amiga header constants
_MAXFONTPATH = 256
_MAXFONTNAME = 32

# file ids
# https://wiki.amigaos.net/wiki/Graphics_Library_and_Text#The_Composition_of_a_Bitmap_Font_on_Disk
_FCH_ID = 0x0f00
_TFCH_ID = 0x0f02

# hunk ids
# http://amiga-dev.wikidot.com/file-format:hunk
_HUNK_HEADER = 0x3f3
_HUNK_CODE = 0x3e9
_HUNK_RELOC32 = 0x3ec
_HUNK_END = 0x3f2

# tf_Flags values
_TF_FLAGS = be.Struct(
    # 0x80 the font has been removed
    FPF_REMOVED=flag,
    # 0x40 size explicitly designed, not constructed
    FPF_DESIGNED=flag,
    # 0x20 character sizes can vary from nominal
    FPF_PROPORTIONAL=flag,
    # 0x10 This font was designed for a Lores Interlaced screen (320x400 NTSC)
    FPF_WIDEDOT=flag,
    # 0x08 This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
    FPF_TALLDOT=flag,
    # 0x04 This font is designed to be printed from from right to left
    FPF_REVPATH=flag,
    # 0x02 font is from diskfont.library
    FPF_DISKFONT=flag,
    # 0x01 font is in rom
    FPF_ROMFONT=flag
)

# tf_Style values
_TF_STYLE = be.Struct(
    # 0x80 the TextAttr is really a TTextAttr
    FSF_TAGGED=flag,
    # 0x40 this uses ColorTextFont structure
    FSF_COLORFONT=flag,
    unused=bitfield('B', 2),
    # 0x08 extended face (wider than normal)
    FSF_EXTENDED=flag,
    # 0x04 italic (slanted 1:2 right)
    FSF_ITALIC=flag,
    # 0x02 bold face text (OR-ed w/ shifted)
    FSF_BOLD=flag,
    # 0x01 underlined (under baseline)
    FSF_UNDERLINED=flag,
)

# Amiga hunk file header
# http://amiga-dev.wikidot.com/file-format:hunk#toc6
#   hunk_id = uint32
#   null-null-terminated string table
_HUNK_FILE_HEADER_1 = be.Struct(
    table_size='uint32',
    first_hunk='uint32',
    last_hunk='uint32',
)
#   hunk_sizes = uint32 * (last_hunk-first_hunk+1)

# disk font header
_AMIGA_HEADER = be.Struct(
    # struct DiskFontHeader
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node05F9.html#line61
    dfh_NextSegment='I',
    dfh_ReturnCode='I',
    # struct Node
    # http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    dfh_ln_Succ='I',
    dfh_ln_Pred='I',
    dfh_ln_Type='B',
    dfh_ln_Pri='b',
    dfh_ln_Name='I',
    dfh_FileID='H',
    dfh_Revision='H',
    dfh_Segment='i',
    # use array of bytes instead of char, to preserve tags post NUL
    dfh_Name=struct.uint8 * _MAXFONTNAME,
    # struct Message at start of struct TextFont
    # struct Message http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node02EF.html
    tf_ln_Succ='I',
    tf_ln_Pred='I',
    tf_ln_Type='B',
    tf_ln_Pri='b',
    tf_ln_Name='I',
    tf_mn_ReplyPort='I',
    tf_mn_Length='H',
    # struct TextFont http://amigadev.elowar.com/read/ADCD_2.1/Libraries_Manual_guide/node03DE.html
    tf_YSize='H',
    tf_Style=_TF_STYLE,
    tf_Flags=_TF_FLAGS,
    tf_XSize='H',
    tf_Baseline='H',
    tf_BoldSmear='H',
    tf_Accessors='H',
    tf_LoChar='B',
    tf_HiChar='B',
    tf_CharData='I',
    tf_Modulo='H',
    tf_CharLoc='I',
    tf_CharSpace='I',
    tf_CharKern='I',
)

# struct FontContentsHeader
# .font directory file
# https://wiki.amigaos.net/wiki/Graphics_Library_and_Text#Composition_of_a_Bitmap_Font_on_Disk
_FONT_CONTENTS_HEADER = be.Struct(
    fch_FileID='uword',
    fch_NumEntries='uword',
    # followed by array of FontContents or TFontContents
)

# struct FontContents
_FONT_CONTENTS = be.Struct(
    fc_FileName=struct.char * _MAXFONTPATH,
    fc_YSize='uword',
    fc_Style='ubyte',
    fc_Flags='ubyte',
)

# struct TFontContents
# not used - we ignore the extra tags stored at the back of the tfc_FileName field
_T_FONT_CONTENTS = be.Struct(
    tfc_FileName=struct.char * (_MAXFONTPATH-2),
    tfc_TagCount='uword',
    tfc_YSize='uword',
    tfc_Style='ubyte',
    tfc_Flags='ubyte',
)


###################################################################################################
# read Amiga font


def _load_amiga(f, where):
    """Load font from Amiga disk font file."""
    # read & ignore header
    _read_header(f)
    amiga_props, glyphs = _read_font_hunk(f)
    logging.info('Amiga properties:')
    for name, value in vars(amiga_props).items():
        logging.info('    %s: %s', name, value)
    props, glyphs = _convert_amiga_font(amiga_props, glyphs)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    return Font(glyphs, properties=vars(props))


def _read_library_names(f):
    library_names = []
    while True:
        num_longs = be.uint32.read_from(f)
        if not num_longs:
            return library_names
        string = f.read(num_longs * 4)
        # http://amiga-dev.wikidot.com/file-format:hunk#toc6
        # - partitions the read string at null terminator and breaks on empty
        # https://archive.org/details/AmigaDOS_Technical_Reference_Manual_1985_Commodore/page/n27/mode/2up
        # - suggests this can't happen, length uint32 must be zero
        # - also parse_header() at https://github.com/cnvogelg/amitools/blob/master/amitools/binfmt/hunk/HunkReader.py
        library_names.append(string)

def _read_header(f):
    """Read file header."""
    # read header id
    hunk_id = be.uint32.read_from(f)
    if hunk_id != _HUNK_HEADER:
        raise FileFormatError(
            'Not an Amiga font data file: '
            f'magic constant 0x{hunk_id:03X} != 0x{_HUNK_HEADER:03X}'
        )
    library_names = _read_library_names(f)
    hfh1 = _HUNK_FILE_HEADER_1.read_from(f)
    # list of memory sizes of hunks in this file (in number of ULONGs)
    # this seems to exclude overhead, so not useful to determine disk sizes
    num_sizes = hfh1.last_hunk - hfh1.first_hunk + 1
    hunk_sizes = be.uint32.array(num_sizes).read_from(f)
    return library_names, hfh1, hunk_sizes

def _read_font_hunk(f):
    """Parse the font data blob."""
    hunk_id = be.uint32.read_from(f)
    if hunk_id != _HUNK_CODE:
        raise FileFormatError(
            'Not an Amiga font data file: '
            f'no code hunk found - id 0x{hunk_id:03X} != 0x{_HUNK_CODE:03X}'
        )
    # location reference point loc = f.tell() + 4
    amiga_props = _AMIGA_HEADER.read_from(f)
    # remainder is the font strike
    glyphs = _read_strike(f, amiga_props)
    return amiga_props, glyphs

def _read_strike(f, props):
    """Read and interpret the font strike and related tables."""
    # remainder is the font strike
    data = f.read()
    # the reference point for offsets in the hunk is just after the ReturnCode
    loc = - _AMIGA_HEADER.size + 4
    # location data
    # one additional for default glyph
    nchars = (props.tf_HiChar - props.tf_LoChar + 1) + 1
    loc_struct = be.Struct(offset='H', width='H')
    locs = loc_struct.array(nchars).from_bytes(data, loc + props.tf_CharLoc)
    # spacing table
    # spacing can be negative
    if props.tf_Flags.FPF_PROPORTIONAL and props.tf_CharSpace:
        spacing = be.int16.array(nchars).from_bytes(data, loc + props.tf_CharSpace)
    else:
        spacing = [props.tf_XSize] * nchars
    # kerning table
    # amiga "kerning" is a horizontal offset; can be pos (to right) or neg
    if props.tf_CharKern:
        kerning = be.int16.array(nchars).from_bytes(data, loc + props.tf_CharKern)
    else:
        kerning = [0] * nchars
    # bitmap strike
    strike = [
        bytes_to_bits(data[_offset : _offset+props.tf_Modulo])
        for _offset in range(
            loc + props.tf_CharData,
            loc + props.tf_CharData + props.tf_Modulo*props.tf_YSize,
            props.tf_Modulo
        )
    ]
    # extract glyphs
    pixels = [
        [_row[_loc.offset:_loc.offset+_loc.width] for _row in strike]
        for _loc in locs
    ]
    glyphs = [
        Glyph(_pix, codepoint=_ord, kerning=_kern, spacing=_spc)
        for _ord, (_pix, _kern, _spc) in enumerate(
            zip(pixels, kerning, spacing),
            start=props.tf_LoChar
        )
    ]
    return glyphs


###################################################################################################
# convert from Amiga to monobit

def _convert_amiga_font(amiga_props, glyphs):
    """Convert Amiga properties and glyphs to monobit Font."""
    glyphs = _convert_amiga_glyphs(glyphs, amiga_props)
    props = _convert_amiga_props(amiga_props)
    return props, glyphs


def _convert_amiga_glyphs(glyphs, amiga_props):
    """Deal with negative kerning by turning it into a global negative offset."""
    # apply kerning and spacing
    glyphs = [
        _glyph.modify(
            offset=Coord(_glyph.kerning, -(amiga_props.tf_YSize - amiga_props.tf_Baseline)),
            advance=_glyph.spacing
        )
        for _glyph in glyphs
    ]
    glyphs = [
        _glyph.drop_properties('kerning', 'spacing')
        for _glyph in glyphs
    ]
    # default glyph has no codepoint
    glyphs[-1] = glyphs[-1].modify(codepoint=(), tags=('default',))
    return glyphs


def _convert_amiga_props(amiga_props):
    """Convert AmigaFont properties into yaff properties."""
    if amiga_props.tf_Style.FSF_COLORFONT:
        raise FileFormatError('Amiga ColorFont not supported')
    props = Props()
    props.amiga = Props()
    # preserve tags stored in name field after \0
    name, *tags = bytes(amiga_props.dfh_Name).decode(_ENCODING).split('\0')
    if name:
        props.name = name.strip()
    tags = [_t.strip() for _t in tags if _t.strip()]
    if tags:
        props.amiga.dfh_Name = f'"{name}"' + ' '.join(tags)
    props.revision = amiga_props.dfh_Revision
    #props.offset = Coord(offset_x, -(amiga_props.tf_YSize - amiga_props.tf_Baseline))
    # tf_Style
    props.weight = 'bold' if amiga_props.tf_Style.FSF_BOLD else Font.default('weight')
    props.slant = 'italic' if amiga_props.tf_Style.FSF_ITALIC else Font.default('slant')
    props.setwidth = 'expanded' if amiga_props.tf_Style.FSF_EXTENDED else Font.default('setwidth')
    if amiga_props.tf_Style.FSF_UNDERLINED:
        props.decoration = 'underline'
    # tf_Flags
    props.spacing = (
        'proportional' if amiga_props.tf_Flags.FPF_PROPORTIONAL else 'monospace'
    )
    if amiga_props.tf_Flags.FPF_REVPATH:
        props.direction = 'right-to-left'
    if amiga_props.tf_Flags.FPF_TALLDOT and not amiga_props.tf_Flags.FPF_WIDEDOT:
        # TALLDOT: This font was designed for a Hires screen (640x200 NTSC, non-interlaced)
        props.pixel_aspect = '1 2'
    elif amiga_props.tf_Flags.FPF_WIDEDOT and not amiga_props.tf_Flags.FPF_TALLDOT:
        # WIDEDOT: This font was designed for a Lores Interlaced screen (320x400 NTSC)
        props.pixel_aspect = '2 1'
    props.encoding = _ENCODING
    props.default_char = 'default'
    # preserve unparsed properties
    # tf_BoldSmear; /* smear to affect a bold enhancement */
    # use the most common value 1 as a default
    if amiga_props.tf_BoldSmear != 1:
        props.amiga.tf_BoldSmear = amiga_props.tf_BoldSmear
    if 'name' in props:
        props.family = props.name.split('/')[0].split(' ')[0]
    return props
