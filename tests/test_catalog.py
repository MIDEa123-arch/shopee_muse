import unittest

from app.recommender.catalog import has_matching_demo_photo,product_kind


class DemoPhotoTests(unittest.TestCase):
    def test_speaker_card_cannot_use_an_earbud_photo(self):
        item={'category_id':2,'name':'Loa Bluetooth JBL Charge 5',
              'image_url':'/static/images/catalog/6b21cdaff41ae221.jpg'}
        self.assertFalse(has_matching_demo_photo(item))
        item['image_url']='/static/images/catalog/c366d5473a83e25f.jpg'
        self.assertTrue(has_matching_demo_photo(item))

    def test_overear_headphones_and_stands_are_not_presented_as_earbuds(self):
        item={'category_id':2,'name':'Tai Nghe Chụp Tai Sony WH-1000XM5',
              'image_url':'/static/images/catalog/6b21cdaff41ae221.jpg'}
        self.assertFalse(has_matching_demo_photo(item))
        item['image_url']='/static/images/catalog/50867512f65f1c41.jpg'
        self.assertTrue(has_matching_demo_photo(item))
        item['name']='Chân Đế Để Bàn Chống Rung Tai Nghe'
        self.assertFalse(has_matching_demo_photo(item))

    def test_bag_with_laptop_in_its_name_is_not_a_laptop(self):
        self.assertNotEqual(product_kind('Balo Laptop Chống Nước'),'laptop')
        self.assertEqual(product_kind('Laptop ASUS ROG Strix'),'laptop')
