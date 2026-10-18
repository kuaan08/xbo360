"""RTTI-less PowerPC candidate scanner tests with synthetic big-endian data."""
import unittest

from ppc_pointer_tables import scan_tables


class PointerTableTests(unittest.TestCase):
    BASE = 0x82000000

    def test_consecutive_code_pointers_without_rtti_are_reported(self):
        image = bytearray(0x400)
        for offset, address in [(0x104, 0x82000200), (0x108, 0x82000220),
                                (0x10C, 0x82000228), (0x110, 0x82000220)]:
            image[offset:offset + 4] = address.to_bytes(4, "big")
        result = scan_tables(
            bytes(image), base=self.BASE,
            data_ranges=[(self.BASE + 0x100, self.BASE + 0x140)],
            executable_ranges=[(self.BASE + 0x200, self.BASE + 0x300)]
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["data_address"], "0x82000104")
        self.assertEqual(result[0]["slot_count"], 4)
        self.assertTrue(result[0]["not_a_function_boundary"])
        self.assertIn("candidate", result[0]["confidence"])

    def test_isolated_pointer_and_unaligned_pointer_not_reported(self):
        image = bytearray(0x400)
        image[0x100:0x104] = (self.BASE + 0x200).to_bytes(4, "big")
        image[0x104:0x108] = (self.BASE + 0x201).to_bytes(4, "big")
        self.assertEqual(scan_tables(bytes(image), base=self.BASE,
                         data_ranges=[(self.BASE + 0x100, self.BASE + 0x120)],
                         executable_ranges=[(self.BASE + 0x200, self.BASE + 0x300)]), [])

    def test_reject_out_of_bounds(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            scan_tables(bytes(128), base=self.BASE,
                        data_ranges=[(self.BASE, self.BASE + 256)],
                        executable_ranges=[(self.BASE, self.BASE + 40)])

    def test_no_auto_function_registration_or_guess(self):
        image = bytearray(0x400)
        for i in range(3):
            image[0x100 + i * 4:0x104 + i * 4] = (self.BASE + 0x200).to_bytes(4, "big")
        results = scan_tables(bytes(image), base=self.BASE,
                              data_ranges=[(self.BASE + 0x100, self.BASE + 0x140)],
                              executable_ranges=[(self.BASE + 0x200, self.BASE + 0x300)])
        self.assertEqual(results[0]["distinct_targets"], 1)
        self.assertNotIn("size", results[0])


if __name__ == "__main__":
    unittest.main()
