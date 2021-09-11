"""
Basic monobit test coverage

usage::

    $ python3 -m tests.test_monobit

    $ coverage run tests/test_monobit.py
    $ coverage report monobit/*py
"""

import os
import tempfile
import unittest
from pathlib import Path

import monobit

class TestMonobit(unittest.TestCase):
    """Test monobit export/import"""

    def setUp(self):
        self.fixed4x6 = monobit.load("tests/fonts/fixed/4x6.yaff")
        self.fixed8x16 = monobit.load("tests/fonts/fixed/8x16.hex") # derivative of Fixed 4x6
        self.tmp_dir = tempfile.TemporaryDirectory()

    def test_import_bdf(self):
        """Test importing bdf files"""
        font = monobit.load("tests/fonts/fixed/4x6.bdf")
        self.assertEqual(len(font.glyphs), 919)

    def test_export_bdf(self):
        """Test exporting bdf files"""
        bdf_file = self.tmp_dir.name + "/4x6.bdf"
        monobit.save(self.fixed4x6, bdf_file)
        self.assertTrue(os.path.getsize(bdf_file) > 0)

    def test_import_draw(self):
        """Test importing draw files"""
        font = monobit.load("tests/fonts/fixed/8x16.draw")
        self.assertEqual(len(font.glyphs), 919)

    def test_export_draw(self):
        """Test exporting draw files"""
        draw_file = self.tmp_dir.name + "/8x16.draw"
        monobit.save(self.fixed8x16, draw_file)
        self.assertTrue(os.path.getsize(draw_file) > 0)

    def test_import_fon(self):
        """Test importing fon files"""
        pack = monobit.load("tests/fonts/fixed/6x13.fon")
        font = pack[0]
        self.assertEqual(len(font.glyphs), 256)

    def test_export_fon(self):
        """Test exporting fon files"""
        fon_file = self.tmp_dir.name + "/4x6.fon"
        monobit.save(self.fixed4x6, fon_file)
        self.assertTrue(os.path.getsize(fon_file) > 0)

    def test_import_fnt(self):
        """Test importing fnt files"""
        font = monobit.load("tests/fonts/fixed/6x13.fnt")
        self.assertEqual(len(font.glyphs), 256)

    def test_export_fnt(self):
        """Test exporting fnt files"""
        fnt_file = self.tmp_dir.name + "/4x6.fnt"
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_hex(self):
        """Test importing hex files"""
        self.assertEqual(len(self.fixed8x16.glyphs), 919)

    def test_export_hex(self):
        """Test exporting hex files"""
        hex_file = self.tmp_dir.name + "/8x16.hex"
        monobit.save(self.fixed8x16, hex_file)
        self.assertTrue(os.path.getsize(hex_file) > 0)

    def test_export_pdf(self):
        """Test exporting pdf files"""
        pdf_file = self.tmp_dir.name + "/4x6.pdf"
        monobit.save(self.fixed4x6, pdf_file)
        self.assertTrue(os.path.getsize(pdf_file) > 0)

    def test_export_png(self):
        """Test exporting png files"""
        png_file = self.tmp_dir.name + "/4x6.png"
        monobit.save(self.fixed4x6, png_file)
        self.assertTrue(os.path.getsize(png_file) > 0)

    def test_import_psf(self):
        """Test importing psf files"""
        font = monobit.load("tests/fonts/fixed/4x6.psf")
        self.assertEqual(len(font.glyphs), 919)

    def test_export_psf(self):
        """Test exporting psf files"""
        psf_file = self.tmp_dir.name + "/4x6.psf"
        monobit.save(self.fixed4x6, psf_file)
        self.assertTrue(os.path.getsize(psf_file) > 0)

    def test_import_yaff(self):
        """Test importing yaff files"""
        self.assertEqual(len(self.fixed4x6.glyphs), 919)

    def test_export_yaff(self):
        """Test exporting yaff files"""
        yaff_file = self.tmp_dir.name + "/4x6.yaff"
        monobit.save(self.fixed4x6, yaff_file)
        self.assertTrue(os.path.getsize(yaff_file) > 0)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_import_raw(self):
        """Test importing raw binary files"""
        font = monobit.load("tests/fonts/fixed/4x6.raw", cell=(4, 6))
        self.assertEqual(len(font.glyphs), 919)

    def test_export_raw(self):
        """Test exporting raw binary files"""
        fnt_file = self.tmp_dir.name + "/4x6.raw"
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_export_pdf(self):
        """Test exporting to pdf."""
        fnt_file = Path(self.tmp_dir.name) / '4x6.pdf'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_bmf(self):
        """Test importing bmfont files."""
        pack = monobit.load("tests/fonts/fixed/6x13.bmf")
        self.assertEqual(len(pack), 7)

    def test_export_bmf(self):
        """Test exporting bmfont files."""
        fnt_file = Path(self.tmp_dir.name) / '4x6.bmf'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_c(self):
        """Test importing c source files."""
        font = monobit.load(
            'tests/fonts/fixed/4x6.c',
            identifier='char font_Fixed_Medium_6', cell=(4, 6)
        )
        self.assertEqual(len(font.glyphs), 919)

    def test_export_c(self):
        """Test exporting c source files."""
        fnt_file = Path(self.tmp_dir.name) / '4x6.c'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

    def test_import_png(self):
        """Test importing image files."""
        font = monobit.load('tests/fonts/fixed/4x6.png', cell=(4, 6), n_chars=919)
        self.assertEqual(len(font.glyphs), 919)

    def test_export_png(self):
        """Test exporting image files."""
        fnt_file = Path(self.tmp_dir.name) / '4x6.png'
        monobit.save(self.fixed4x6, fnt_file)
        self.assertTrue(os.path.getsize(fnt_file) > 0)

if __name__ == '__main__':
    unittest.main()
