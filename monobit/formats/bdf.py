"""
monobit.bdf - Adobe Glyph Bitmap Distribution Format

(c) 2019--2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging

from ..binary import int_to_bytes, bytes_to_int
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font, Coord
from ..glyph import Glyph
from ..encoding import charmaps
from ..taggers import tagmaps


# BDF specification: https://adobe-type-tools.github.io/font-tech-notes/pdfs/5005.BDF_Spec.pdf
# XLFD conventions: https://www.x.org/releases/X11R7.6/doc/xorg-docs/specs/XLFD/xlfd.html
# charset and property registry: https://github.com/freedesktop/xorg-docs/blob/master/registry

# https://github.com/freedesktop/xorg-docs/blob/master/registry
#
# 14. FONT CHARSET (REGISTRY AND ENCODING) NAMES
#
# See Sections 3.1.2.12 of the XLFD.  For ISO standards, the format
# will generally be: "ISO" + <standard-number> + "-" + <part-number>
#
# Name						Reference
# ----						---------
# "DEC"						[27]
# 	registry prefix
# "DEC.CNS11643.1986-2"				[53]
# 	CNS11643 2-plane using the encoding
# 	suggested in that standard
# "DEC.DTSCS.1990-2"				[54]
# 	DEC Taiwan Supplemental Character Set
# "fujitsu.u90x01.1991-0"				[87]
# "fujitsu.u90x03.1991-0"				[87]
# "GB2312.1980-0"					[39],[12]
# 	China (PRC) Hanzi, GL encoding
# "GB2312.1980-1"					[39]
# 	(deprecated)
# 	China (PRC) Hanzi, GR encoding
# "HP-Arabic8"					[36]
# 	HPARABIC8 8-bit character set
# "HP-East8"					[36]
# 	HPEAST8 8-bit character set
# "HP-Greek8"					[36]
# 	HPGREEK8 8-bit character set
# "HP-Hebrew8"					[36]
# 	HPHEBREW8 8-bit character set
# "HP-Japanese15"					[36]
# 	HPJAPAN15 15-bit characer set,
# 	modified from industry defacto
# 	standard Shift-JIS
# "HP-Kana8"					[36]
# 	HPKANA8 8-bit character set
# "HP-Korean15"					[36]
# 	HPKOREAN15 15-bit character set
# "HP-Roman8"					[36]
# 	HPROMAN8 8-bit character set
# "HP-SChinese15"					[36]
# 	HPSCHINA15 15-bit character set for
# 	support of Simplified Chinese
# "HP-TChinese15"					[36]
# 	HPTCHINA15 15-bit character set for
# 	support of Traditional Chinese
# "HP-Turkish8"					[36]
# 	HPTURKISH8 8-bit character set
# "IPSYS"						[59]
# 	registry prefix
# "IPSYS.IE-1"					[59]
# "ISO2022"<REG>"-"<ENC>				[44]
# "ISO646.1991-IRV"				[107]
# 	ISO 646 International Reference Version
# "ISO8859-1"					[15],[12]
# 	ISO Latin alphabet No. 1
# "ISO8859-2"					[15],[12]
# 	ISO Latin alphabet No. 2
# "ISO8859-3"					[15],[12]
# 	ISO Latin alphabet No. 3
# "ISO8859-4"					[15],[12]
# 	ISO Latin alphabet No. 4
# "ISO8859-5"					[15],[12]
# 	ISO Latin/Cyrillic alphabet
# "ISO8859-6"					[15],[12]
# 	ISO Latin/Arabic alphabet
# "ISO8859-7"					[15],[12]
# 	ISO Latin/Greek alphabet
# "ISO8859-8"					[15],[12]
# 	ISO Latin/Hebrew alphabet
# "ISO8859-9"					[15],[12]
# 	ISO Latin alphabet No. 5
# "ISO8859-10"					[15],[12]
# 	ISO Latin alphabet No. 6
# "ISO8859-13"					[15],[12]
# 	ISO Latin alphabet No. 7
# "ISO8859-14"					[15],[12]
# 	ISO Latin alphabet No. 8
# "ISO8859-15"					[15],[12]
# 	ISO Latin alphabet No. 9
# "ISO8859-16"					[15],[12]
# 	ISO Latin alphabet No. 10
# "FCD8859-15"					[7]
# 	(deprecated)
# 	ISO Latin alphabet No. 9, Final Committee Draft
# "ISO10646-1"					[133]
# 	Unicode Universal Multiple-Octet Coded Character Set
# "ISO10646-MES"					[133]
# 	(deprecated)
# 	Unicode Minimum European Subset
# "JISX0201.1976-0"				[38],[12]
# 	8-Bit Alphanumeric-Katakana Code
# "JISX0208.1983-0"				[40],[12]
# 	Japanese Graphic Character Set,
# 	GL encoding
# "JISX0208.1990-0"				[71]
# 	Japanese Graphic Character Set,
# 	GL encoding
# "JISX0208.1983-1"				[40]
# 	(deprecated)
# 	Japanese Graphic Character Set,
# 	GR encoding
# "JISX0212.1990-0"				[72]
# 	Supplementary Japanese Graphic Character Set,
# 	GL encoding
# "KOI8-R"					[119]
# 	Cyrillic alphabet
# "KSC5601.1987-0"				[41],[12]
# 	Korean Graphic Character Set,
# 	GL encoding
# "KSC5601.1987-1"				[41]
# 	(deprecated)
# 	Korean Graphic Character Set,
# 	GR encoding
# "omron_CNS11643-0"				[45]
# "omron_CNS11643-1"				[45]
# "omron_BIG5-0"					[45]
# "omron_BIG5-1"					[45]
# "wn.tamil.1993"					[103]


# https://www.freshports.org/x11-fonts/encodings/
#
# share/fonts/encodings/adobe-dingbats.enc.gz
# share/fonts/encodings/adobe-standard.enc.gz
# share/fonts/encodings/adobe-symbol.enc.gz
# share/fonts/encodings/armscii-8.enc.gz
# share/fonts/encodings/ascii-0.enc.gz
# share/fonts/encodings/dec-special.enc.gz
# share/fonts/encodings/encodings.dir
# share/fonts/encodings/ibm-cp437.enc.gz
# share/fonts/encodings/ibm-cp850.enc.gz
# share/fonts/encodings/ibm-cp852.enc.gz
# share/fonts/encodings/ibm-cp866.enc.gz
# share/fonts/encodings/iso8859-11.enc.gz
# share/fonts/encodings/iso8859-13.enc.gz
# share/fonts/encodings/iso8859-16.enc.gz
# share/fonts/encodings/iso8859-6.16.enc.gz
# share/fonts/encodings/iso8859-6.8x.enc.gz
# share/fonts/encodings/large/big5.eten-0.enc.gz
# share/fonts/encodings/large/big5hkscs-0.enc.gz
# share/fonts/encodings/large/cns11643-1.enc.gz
# share/fonts/encodings/large/cns11643-2.enc.gz
# share/fonts/encodings/large/cns11643-3.enc.gz
# share/fonts/encodings/large/encodings.dir
# share/fonts/encodings/large/gb18030-0.enc.gz
# share/fonts/encodings/large/gb18030.2000-0.enc.gz
# share/fonts/encodings/large/gb18030.2000-1.enc.gz
# share/fonts/encodings/large/gb2312.1980-0.enc.gz
# share/fonts/encodings/large/gbk-0.enc.gz
# share/fonts/encodings/large/jisx0201.1976-0.enc.gz
# share/fonts/encodings/large/jisx0208.1990-0.enc.gz
# share/fonts/encodings/large/jisx0212.1990-0.enc.gz
# share/fonts/encodings/large/ksc5601.1987-0.enc.gz
# share/fonts/encodings/large/ksc5601.1992-3.enc.gz
# share/fonts/encodings/large/sun.unicode.india-0.enc.gz
# share/fonts/encodings/microsoft-cp1250.enc.gz
# share/fonts/encodings/microsoft-cp1251.enc.gz
# share/fonts/encodings/microsoft-cp1252.enc.gz
# share/fonts/encodings/microsoft-cp1253.enc.gz
# share/fonts/encodings/microsoft-cp1254.enc.gz
# share/fonts/encodings/microsoft-cp1255.enc.gz
# share/fonts/encodings/microsoft-cp1256.enc.gz
# share/fonts/encodings/microsoft-cp1257.enc.gz
# share/fonts/encodings/microsoft-cp1258.enc.gz
# share/fonts/encodings/microsoft-win3.1.enc.gz
# share/fonts/encodings/mulearabic-0.enc.gz
# share/fonts/encodings/mulearabic-1.enc.gz
# share/fonts/encodings/mulearabic-2.enc.gz
# share/fonts/encodings/mulelao-1.enc.gz
# share/fonts/encodings/suneu-greek.enc.gz
# share/fonts/encodings/tcvn-0.enc.gz
# share/fonts/encodings/tis620-2.enc.gz
# share/fonts/encodings/viscii1.1-1.enc.gz

# https://x.org/releases/X11R7.7/doc/xorg-docs/fonts/fonts.html
# > Specifying an encoding value of
# > adobe-fontspecific for a Type 1 font disables the encoding mechanism. This is useful with symbol
# > and incorrectly encoded fonts (see Hints about using badly encoded fonts below).
#
# > In the case of Type 1 fonts, the font designer can specify a default encoding; this encoding is
# > requested by using the “adobe-fontspecific” encoding in the XLFD name.

# some more encodings mentioned here:
# https://www.x.org/releases/X11R6.9.0/doc/html/fonts3.html
# https://www.x.org/releases/X11R6.9.0/doc/html/fonts4.html
#
# ISO10646-1 = unicode
# ISO8859-1 (etc)  = latin-1
# KOI8-R (-U -RU -UNI -E)
# fontspecific-0
# microsoft-symbol
# apple-roman
# ibm-cp437
# adobe-standard
# adobe-dingbats
# adobe-symbol
# adobe-fontspecific
# microsoft-cp1252
# microsoft-win3.1
# jisx0208.1990-0
# jisx0201.1976-0
# big5.eten-0
# gb2312.1980-0

# X11 / BDF undefined
# these are mapped to "no encoding"
# "no encoding" is mapped to the first name provided here
_UNDEFINED_ENCODINGS = [
    'fontspecific-0',
    'adobe-fontspecific',
]

# names to be used when writing bdf
_UNIX_ENCODINGS = {
    '': _UNDEFINED_ENCODINGS[0],
    'unicode': 'ISO10646-1',
    'ascii': 'ascii-0',

    'latin-1': 'ISO8859-1',
    'latin-2': 'ISO8859-2',
    'latin-3': 'ISO8859-3',
    'latin-4': 'ISO8859-4',
    'iso8859-5': 'ISO8859-5',
    'iso8859-6': 'ISO8859-6',
    'iso8859-7': 'ISO8859-7',
    'iso8859-8': 'ISO8859-8',
    'iso8859-9': 'ISO8859-9',
    'iso8859-10': 'ISO8859-10',
    'iso8859-11': 'ISO8859-11',
    'iso8859-13': 'ISO8859-13',
    'iso8859-14': 'ISO8859-14',
    'iso8859-15': 'ISO8859-15',
    'iso8859-16': 'ISO8859-16',

    'koi8-r': 'KOI8-R',
    'koi8-u': 'KOI8-U',
    'koi8-ru': 'KOI8-RU',
    'koi8-e': 'KOI8-E',
    'koi8-unified': 'KOI8-UNI',

    'mac-symbol': 'microsoft-symbol',
    'mac-roman': 'apple-roman',
    'cp437': 'ibm-cp437',
    'cp850': 'ibm-cp850',
    'cp852': 'ibm-cp852',
    'cp866': 'ibm-cp866',

    # adobe, dec encodings have standard names

    'windows-1250': 'microsoft-cp1250',
    'windows-1251': 'microsoft-cp1251',
    'windows-1252': 'microsoft-cp1252',
    'windows-1253': 'microsoft-cp1253',
    'windows-1254': 'microsoft-cp1254',
    'windows-1255': 'microsoft-cp1255',
    'windows-1256': 'microsoft-cp1256',
    'windows-1257': 'microsoft-cp1257',
    'windows-1258': 'microsoft-cp1258',
    'windows-3.1': 'microsoft-win3.1',

    'hp-roman8': 'HP-Roman8',
    'hp-greek8': 'HP-Greek8',
    'hp-thai8': 'HP-Thai8',
    'hp-turkish8': 'HP-Turkish8',

    'jis-x0201': 'jisx0201.1976-0',

    'big5-hkscs': 'big5hkscs-0',
    'windows-936': 'gbk-0',

    # johab
    'windows-1361': 'ksc5601.1992-3',
    # ksc5601.1987-0

    'tis-620': 'tis620-0',
    'viscii': 'viscii1.1-1',
    # tcvn-0 ?

    # big5.eten-0
    # gb2312.1980-0
    # cns11643-1
    # cns11643-2
    # cns11643-3
    # gb18030-0
    # gb18030.2000-0
    # gb18030.2000-1

    # jisx0208.1990-0
    # jisx0212.1990-0
}

_SLANT_MAP = {
    'R': 'roman',
    'I': 'italic',
    'O': 'oblique',
    'RO': 'reverse-oblique',
    'RI': 'reverse-italic',
    'OT': '', # 'other'
}

_SPACING_MAP = {
    'P': 'proportional',
    'M': 'monospace',
    'C': 'character-cell',
}

_SETWIDTH_MAP = {
    '0': '', # Undefined or unknown
    '10': 'ultra-condensed',
    '20': 'extra-condensed',
    '30': 'condensed', # Condensed, Narrow, Compressed, ...
    '40': 'semi-condensed',
    '50': 'medium', # Medium, Normal, Regular, ...
    '60': 'semi-expanded', # SemiExpanded, DemiExpanded, ...
    '70': 'expanded',
    '80': 'extra-expanded', # ExtraExpanded, Wide, ...
    '90': 'ultra-expanded',
}

_WEIGHT_MAP = {
    '0': '', # Undefined or unknown
    '10': 'thin', # UltraLight
    '20': 'extra-light',
    '30': 'light',
    '40': 'semi-light', # SemiLight, Book, ...
    '50': 'regular', # Medium, Normal, Regular,...
    '60': 'semi-bold', # SemiBold, DemiBold, ...
    '70': 'bold',
    '80': 'extra-bold', # ExtraBold, Heavy, ...
    '90': 'heavy', # UltraBold, Black, ...,
}

# fields of the xlfd font name
_XLFD_NAME_FIELDS = (
    '',
    'FOUNDRY',
    'FAMILY_NAME',
    'WEIGHT_NAME',
    'SLANT',
    'SETWIDTH_NAME',
    'ADD_STYLE_NAME',
    'PIXEL_SIZE',
    'POINT_SIZE',
    'RESOLUTION_X',
    'RESOLUTION_Y',
    'SPACING',
    'AVERAGE_WIDTH',
    'CHARSET_REGISTRY',
    'CHARSET_ENCODING',
)

# unparsed xlfd properties, for reference
_XLFD_UNPARSED = {
    'MIN_SPACE',
    'NORM_SPACE',
    'MAX_SPACE',
    'END_SPACE',
    'AVG_CAPITAL_WIDTH',
    'AVG_LOWERCASE_WIDTH',
    'QUAD_WIDTH',
    'FIGURE_WIDTH',
    'SUPERSCRIPT_X',
    'SUPERSCRIPT_Y',
    'SUBSCRIPT_X',
    'SUBSCRIPT_Y',
    'SUPERSCRIPT_SIZE',
    'SUBSCRIPT_SIZE',
    'SMALL_CAP_SIZE',
    'UNDERLINE_POSITION',
    'UNDERLINE_THICKNESS',
    'STRIKEOUT_ASCENT',
    'STRIKEOUT_DESCENT',
    'ITALIC_ANGLE',
    'WEIGHT',
    'DESTINATION',
    'FONT_TYPE',
    'RASTERIZER_NAME',
    'RASTERIZER_VERSION',
    #'RAW_*',
    'AXIS_NAMES',
    'AXIS_LIMITS',
    'AXIS_TYPES',
}


##############################################################################
# top-level calls

@loaders.register('bdf', magic=(b'STARTFONT ',), name='BDF')
def load_bdf(instream, where=None):
    """
    Load font from Adobe Glyph Bitmap Distribution Format (BDF) file.
    """
    instream = instream.text
    nchars, comments, bdf_props, x_props = _read_bdf_global(instream)
    glyphs, glyph_props = _read_bdf_characters(instream)
    # check number of characters, but don't break if no match
    if nchars != len(glyphs):
        logging.warning('Number of characters found does not match CHARS declaration.')
    glyphs, properties = _parse_properties(glyphs, glyph_props, bdf_props, x_props)
    return Font(glyphs, comments=comments, properties=properties)


@savers.register(linked=load_bdf)
def save_bdf(fonts, outstream, where=None):
    """
    Save font to Adobe Glyph Bitmap Distribution Format (BDF) file.
    """
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to BDF file.')
    _save_bdf(fonts[0], outstream.text)


##############################################################################
# BDF reader

def _read_dict(instream, until=None):
    """Read key-value pairs."""
    result = {}
    for line in instream:
        if not line:
            continue
        if ' ' not in line:
            break
        keyword, values = line[:-1].split(' ', 1)
        result[keyword] = values.strip()
        if keyword == until:
            break
    return result

def _read_bdf_characters(instream):
    """Read character section."""
    # output
    glyphs = []
    glyph_meta = []
    for line in instream:
        line = line.rstrip('\r\n')
        if not line:
            continue
        if line.startswith('ENDFONT'):
            break
        elif not line.startswith('STARTCHAR'):
            raise ValueError('Expected STARTCHAR')
        keyword, values = line.split(' ', 1)
        meta = _read_dict(instream, until='BITMAP')
        meta[keyword] = values
        width, height, _, _ = meta['BBX'].split(' ')
        width, height = int(width), int(height)
        # convert from hex-string to list of bools
        hexstr = ''.join(instream.readline().strip() for _ in range(height))
        glyph = Glyph.from_hex(hexstr, width, height)
        # store labels, if they're not just ordinals
        label = meta['STARTCHAR']
        try:
            int(label)
        except ValueError:
            glyph = glyph.modify(tags=[label])
        # ENCODING must be single integer or -1 followed by integer
        encvalue = int(meta['ENCODING'].split(' ')[-1])
        # no encoding number found
        if encvalue != -1:
            glyph = glyph.modify(codepoint=(encvalue,))
        glyphs.append(glyph)
        glyph_meta.append(meta)
        if not instream.readline().startswith('ENDCHAR'):
            raise('Expected ENDCHAR')
    return glyphs, glyph_meta

def _read_bdf_global(instream):
    """Read global section of BDF file."""
    # read global section
    bdf_props = {}
    x_props = {}
    comments = []
    parsing_x = False
    nchars = -1
    for line in instream:
        line = line.strip('\r\n')
        if not line:
            continue
        elif line.startswith('COMMENT'):
            comments.append(line[8:])
        elif line.startswith('STARTPROPERTIES'):
            parsing_x = True
        elif line.startswith('ENDPROPERTIES'):
            parsing_x = False
        else:
            keyword, values = line.split(' ', 1)
            values = values.strip()
            if keyword == 'CHARS':
                # value equals number of chars
                # this signals the end of the global section
                nchars = int(values)
                comments = '\n'.join(comments)
                return nchars, comments, bdf_props, x_props
            elif parsing_x:
                x_props[keyword] = values
            else:
                # record all keywords in the same metadata table
                bdf_props[keyword] = values
    raise ValueError('No character information found in BDF file.')


##############################################################################
# properties

def _parse_properties(glyphs, glyph_props, bdf_props, x_props):
    """Parse metrics and metadata."""
    logging.info('bdf properties:')
    for name, value in bdf_props.items():
        logging.info('    %s: %s', name, value)
    logging.info('x properties:')
    for name, value in x_props.items():
        logging.info('    %s: %s', name, value)
    # parse meaningful metadata
    glyphs, properties, xlfd_name = _parse_bdf_properties(glyphs, glyph_props, bdf_props)
    xlfd_props = _parse_xlfd_properties(x_props, xlfd_name)
    for key, value in xlfd_props.items():
        if key in properties and properties[key] != value:
            logging.warning(
                'Inconsistency between BDF and XLFD properties: '
                '%s=%s (XLFD) but %s=%s (BDF). Taking BDF property.',
                key, value, key, properties[key]
            )
        else:
            properties[key] = value
    # encoding values above 256 become multi-byte
    # unless we're working in unicode
    if not charmaps.is_unicode(properties['encoding']):
        glyphs = [
            _glyph.modify(codepoint=int_to_bytes(_glyph.codepoint[0]))
            for _glyph in glyphs
            if _glyph.codepoint
        ]
    logging.info('yaff properties:')
    for name, value in properties.items():
        logging.info('    %s: %s', name, value)
    return glyphs, properties


def _parse_bdf_properties(glyphs, glyph_props, bdf_props):
    """Parse BDF global and per-glyph geometry."""
    size_prop = bdf_props.pop('SIZE').split()
    if len(size_prop) > 3:
        if size_prop[3] != 1:
            raise ValueError('Anti-aliasing and colour not supported.')
        size_prop = size_prop[:3]
    size, xdpi, ydpi = size_prop
    properties = {
        'source-format': 'BDF v{}'.format(bdf_props.pop('STARTFONT')),
        'point-size': size,
        'dpi': (xdpi, ydpi),
    }
    properties['revision'] = bdf_props.pop('CONTENTVERSION', '')
    # not supported: METRICSSET != 0
    writing_direction = bdf_props.pop('METRICSSET', 0)
    if writing_direction == 1:
        # top-to-bottom only
        raise ValueError('Top-to-bottom fonts not yet supported.')
    elif writing_direction == 2:
        logging.warning(
            'Top-to-bottom fonts not yet supported. Preserving horizontal metrics only.'
        )
    # global settings, tend to be overridden by per-glyph settings
    global_bbx = bdf_props.pop('FONTBOUNDINGBOX')
    # global DWIDTH; use bounding box as fallback if not specified
    global_dwidth = bdf_props.pop('DWIDTH', global_bbx[:2])
    global_swidth = bdf_props.pop('SWIDTH', 0)
    # convert glyph properties
    mod_glyphs = []
    for glyph, props in zip(glyphs, glyph_props):
        new_props = {}
        # bounding box & offset
        bbx = props.get('BBX', global_bbx)
        bbx_width, bbx_height, offset_x, offset_y = (int(_p) for _p in bbx.split(' '))
        new_props['offset'] = Coord(offset_x, offset_y)
        # advance width
        dwidth = props.get('DWIDTH', global_dwidth)
        dwidth_x, dwidth_y = (int(_p) for _p in dwidth.split(' '))
        new_props['tracking'] = dwidth_x - glyph.width - offset_x
        if dwidth_y:
            raise FileFormatError('Top-to-bottom fonts not yet supported.')
        mod_glyphs.append(glyph.modify(**new_props))
    xlfd_name = bdf_props.pop('FONT')
    # keep unparsed bdf props
    properties.update({
        'bdf.' + _key: _value
        for _key, _value in bdf_props.items()
    })
    return mod_glyphs, properties, xlfd_name


def _parse_xlfd_name(xlfd_str):
    """Parse X logical font description font name string."""
    xlfd = xlfd_str.split('-')
    if len(xlfd) == 15:
        properties = {_key: _value for _key, _value in zip(_XLFD_NAME_FIELDS, xlfd) if _key and _value}
    else:
        logging.warning('Could not parse X font name string `%s`', xlfd_str)
        return {}
    return properties

def _from_quoted_string(quoted):
    """Strip quotes"""
    return quoted.strip('"').replace('""', '"')

def _parse_xlfd_properties(x_props, xlfd_name):
    """Parse X metadata."""
    xlfd_name_props = _parse_xlfd_name(xlfd_name)
    x_props = {**xlfd_name_props, **x_props}
    # PIXEL_SIZE = ROUND((RESOLUTION_Y * POINT_SIZE) / 722.7)
    properties = {
        # FULL_NAME is deprecated
        'name': _from_quoted_string(x_props.pop('FACE_NAME', x_props.pop('FULL_NAME', ''))),
        'revision': _from_quoted_string(x_props.pop('FONT_VERSION', '')),
        'foundry': _from_quoted_string(x_props.pop('FOUNDRY', '')),
        'copyright': _from_quoted_string(x_props.pop('COPYRIGHT', '')),
        'notice': _from_quoted_string(x_props.pop('NOTICE', '')),
        'family': _from_quoted_string(x_props.pop('FAMILY_NAME', '')),
        'style': _from_quoted_string(x_props.pop('ADD_STYLE_NAME', '')).lower(),
        'ascent': x_props.pop('FONT_ASCENT', None),
        'descent': x_props.pop('FONT_DESCENT', None),
        'x-height': x_props.pop('X_HEIGHT', None),
        'cap-height': x_props.pop('CAP_HEIGHT', None),
        'pixel-size': x_props.pop('PIXEL_SIZE', None),
        'slant': _SLANT_MAP.get(_from_quoted_string(x_props.pop('SLANT', '')), None),
        'spacing': _SPACING_MAP.get(_from_quoted_string(x_props.pop('SPACING', '')), None),
    }
    if 'POINT_SIZE' in x_props:
        properties['point-size'] = str(round(int(x_props.pop('POINT_SIZE')) / 10))
    if 'AVERAGE_WIDTH' in x_props:
        # average width can have a tilde for negative - because it occurs in the xlfd font name
        properties['average-advance'] = int(x_props.pop('AVERAGE_WIDTH').replace('~', '-')) / 10
    # prefer the more precise relative weight and setwidth measures
    if 'RELATIVE_SETWIDTH' in x_props:
        properties['setwidth'] = _SETWIDTH_MAP.get(x_props.pop('RELATIVE_SETWIDTH'), None)
        x_props.pop('SETWIDTH_NAME', None)
    if 'setwidth' not in properties or not properties['setwidth']:
        properties['setwidth'] = _from_quoted_string(x_props.pop('SETWIDTH_NAME', '')).lower()
    if 'RELATIVE_WEIGHT' in x_props:
        properties['weight'] = _WEIGHT_MAP.get(x_props.pop('RELATIVE_WEIGHT'), None)
        x_props.pop('WEIGHT_NAME', None)
    if 'weight' not in properties or not properties['weight']:
        properties['weight'] = _from_quoted_string(x_props.pop('WEIGHT_NAME', '')).lower()
    # resolution
    if 'RESOLUTION_X' in x_props and 'RESOLUTION_Y' in x_props:
        properties['dpi'] = (x_props.pop('RESOLUTION_X'), x_props.pop('RESOLUTION_Y'))
        x_props.pop('RESOLUTION', None)
    elif 'RESOLUTION' in x_props:
        # deprecated
        properties['dpi'] = (x_props.get('RESOLUTION'), x_props.pop('RESOLUTION'))
    # encoding
    registry = _from_quoted_string(x_props.pop('CHARSET_REGISTRY', '')).lower()
    encoding = _from_quoted_string(x_props.pop('CHARSET_ENCODING', '')).lower()
    if registry and encoding and encoding != '0':
        properties['encoding'] = f'{registry}-{encoding}'
    elif registry:
        properties['encoding'] = registry
    elif encoding != '0':
        properties['encoding'] = encoding
    if properties['encoding'] in _UNDEFINED_ENCODINGS:
        properties['encoding'] = ''
    if 'DEFAULT_CHAR' in x_props:
        default_ord = int(x_props.pop('DEFAULT_CHAR', None))
        properties['default-char'] = default_ord
    properties = {_k: _v for _k, _v in properties.items() if _v is not None and _v != ''}
    # invalid xlfd name: keep but with changed property name
    if not xlfd_name_props:
        properties['bdf._FONT'] = xlfd_name
    # keep unparsed properties
    properties.update({'bdf.' + _k: _v for _k, _v in x_props.items()})
    return properties


##############################################################################
# BDF writer

def _create_xlfd_name(xlfd_props):
    """Construct XLFD name from properties."""
    xlfd_fields = [xlfd_props.get(prop, '') for prop in _XLFD_NAME_FIELDS]
    return '-'.join(str(_field).strip('"') for _field in xlfd_fields)

def _quoted_string(unquoted):
    """Return quoted version of string, if any."""
    if unquoted:
        return '"{}"'.format(unquoted.replace('"', '""'))
    return ''

def _create_xlfd_properties(font):
    """Construct XLFD properties."""
    xlfd_props = {
        # rendering hints
        'FONT_ASCENT': font.ascent,
        'FONT_DESCENT': font.descent,
        'PIXEL_SIZE': font.pixel_size,
        'X_HEIGHT': font.x_height,
        'CAP_HEIGHT': font.cap_height,
        'RESOLUTION_X': font.dpi.x,
        'RESOLUTION_Y': font.dpi.y,
        'POINT_SIZE': int(font.point_size) * 10,
        'FACE_NAME': _quoted_string(font.name),
        'FONT_VERSION': _quoted_string(font.revision),
        'COPYRIGHT': _quoted_string(font.copyright),
        'NOTICE': _quoted_string(font.notice),
        'FOUNDRY': _quoted_string(font.foundry),
        'FAMILY_NAME': _quoted_string(font.family),
        'WEIGHT_NAME': _quoted_string(font.weight.title()),
        'RELATIVE_WEIGHT': (
            {_v: _k for _k, _v in _WEIGHT_MAP.items()}.get(font.weight, 50)
        ),
        'SLANT': _quoted_string(
            {_v: _k for _k, _v in _SLANT_MAP.items()}.get(font.slant, 'R')
        ),
        'SPACING': _quoted_string(
            {_v: _k for _k, _v in _SPACING_MAP.items()}.get(font.spacing, 'P')
        ),
        'SETWIDTH_NAME': _quoted_string(font.setwidth.title()),
        'RELATIVE_SETWIDTH': (
            # 50 is medium
            {_v: _k for _k, _v in _SETWIDTH_MAP.items()}.get(font.setwidth, 50)
        ),
        'ADD_STYLE_NAME': _quoted_string(font.style.title()),
        'AVERAGE_WIDTH': str(round(float(font.average_advance) * 10)).replace('-', '~'),
    }
    # encoding dependent values
    default_codepoint = font.get_default_glyph().codepoint
    if charmaps.is_unicode(font.encoding):
        if len(default_codepoint) > 1:
            raise ValueError('Default glyph must not be a grapheme sequence.')
        xlfd_props['DEFAULT_CHAR'] = default_codepoint[0]
        # unicode encoding
        xlfd_props['CHARSET_REGISTRY'] = '"ISO10646"'
        xlfd_props['CHARSET_ENCODING'] = '"1"'
    else:
        xlfd_props['DEFAULT_CHAR'] = bytes_to_int(default_codepoint)
        # try preferred name
        encoding_name = _UNIX_ENCODINGS.get(font.encoding, font.encoding)
        registry, *encoding = encoding_name.split('-', 1)
        # encoding
        xlfd_props['CHARSET_REGISTRY'] = _quoted_string(registry.upper())
        if encoding:
            xlfd_props['CHARSET_ENCODING'] = _quoted_string(encoding[0].upper())
        else:
            xlfd_props['CHARSET_ENCODING'] = '"0"'
    # remove empty properties
    xlfd_props = {_k: _v for _k, _v in xlfd_props.items() if _v}
    # keep unparsed BDF properties
    xlfd_props.update({
        _k[len('bdf.'):].replace('-', '_').upper(): _v
        for _k, _v in font.nondefault_properties.items() if _k.startswith('bdf.')
    })
    return xlfd_props

def _save_bdf(font, outstream):
    """Write one font to X11 BDF 2.1."""
    # property table
    xlfd_props = _create_xlfd_properties(font)
    bdf_props = [
        ('STARTFONT', '2.1'),
    ] + [
        ('COMMENT', _comment) for _comment in font.get_comments()
    ] + [
        ('FONT', _create_xlfd_name(xlfd_props)),
        ('SIZE', f'{font.point_size} {font.dpi.x} {font.dpi.y}'),
        (
            # per the example in the BDF spec,
            # the first two coordinates in FONTBOUNDINGBOX are the font's ink-bounds
            'FONTBOUNDINGBOX',
            f'{font.bounding_box.x} {font.bounding_box.y} {font.offset.x} {font.offset.y}'
        )
    ]
    # labels
    # get glyphs for encoding values
    encoded_glyphs = []
    for glyph in font.glyphs:
        if charmaps.is_unicode(font.encoding):
            if len(glyph.codepoint) == 1:
                encoding, = glyph.codepoint
            else:
                # multi-codepoint grapheme cluster or not set
                # -1 means no encoding value in bdf
                encoding = -1
        else:
            # encoding values above 256 become multi-byte
            # unless we're working in unicode
            encoding = bytes_to_int(glyph.codepoint)
        # char must have a name in bdf
        # keep the first tag as the glyph name if available
        if glyph.tags:
            name = glyph.tags[0]
        else:
            # look up in adobe glyph list if character available
            name = tagmaps['adobe'].get_tag(glyph)
            # otherwise, use encoding value if available
            if not name and encoding != -1:
                name = f'char{encoding:02X}'
            if not name:
                logging.warning(
                    f'Multi-codepoint glyph {glyph.codepoint}'
                    "can't be stored as no name or character available."
                )
        encoded_glyphs.append((encoding, name, glyph))
    glyphs = []
    for encoding, name, glyph in encoded_glyphs:
        # "The SWIDTH y value should always be zero for a standard X font."
        # "The DWIDTH y value should always be zero for a standard X font."
        swidth_y, dwidth_y = 0, 0
        # SWIDTH = DWIDTH / ( points/1000 * dpi / 72 )
        # DWIDTH specifies the widths in x and y, dwx0 and dwy0, in device pixels.
        # Like SWIDTH , this width information is a vector indicating the position of
        # the next glyph’s origin relative to the origin of this glyph.
        dwidth_x = font.offset.x + glyph.width + font.tracking
        swidth_x = int(round(dwidth_x / (font.point_size / 1000) / (font.dpi.y / 72)))
        offset_x, offset_y = font.offset.x, font.offset.y
        # minimize glyphs to ink-bounds (BBX) before storing, except "cell" fonts
        if font.spacing not in ('character-cell', 'multi-cell'):
            offset_x, offset_y = offset_x + glyph.ink_offsets[0], offset_y + glyph.ink_offsets[1]
            glyph = glyph.reduce()
        if not glyph.height or not glyph.width:
            # empty glyph
            split_hex = ''
        else:
            hex = glyph.as_hex().upper()
            width = len(hex) // glyph.height
            split_hex = [hex[_offs:_offs+width] for _offs in range(0, len(hex), width)]
        glyphs.append([
            ('STARTCHAR', name),
            ('ENCODING', str(encoding)),
            ('SWIDTH', f'{swidth_x} {swidth_y}'),
            ('DWIDTH', f'{dwidth_x} {dwidth_y}'),
            ('BBX', f'{glyph.width} {glyph.height} {offset_x} {offset_y}'),
            ('BITMAP', '' if not split_hex else '\n' + '\n'.join(split_hex)),
        ])
    # write out
    for key, value in bdf_props:
        if value:
            outstream.write(f'{key} {value}\n')
    if xlfd_props:
        outstream.write(f'STARTPROPERTIES {len(xlfd_props)}\n')
        for key, value in xlfd_props.items():
            outstream.write(f'{key} {value}\n')
        outstream.write('ENDPROPERTIES\n')
    outstream.write(f'CHARS {len(glyphs)}\n')
    for glyph in glyphs:
        for key, value in glyph:
            outstream.write(f'{key} {value}\n')
        outstream.write('ENDCHAR\n')
    outstream.write('ENDFONT\n')
