import unittest
import json
import os
from . import flask_app # Import the module to patch the global variable
from .portfolio import PortfolioStorage

class TestBackend(unittest.TestCase):
    def setUp(self):
        # Patch the global variable in flask_app
        self.original_storage = flask_app.portfolio_storage
        self.test_filename = 'test_portfolio.json'
        # Ensure we are using the correct data dir relative to flask_app
        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        
        # Initialize test storage
        self.test_storage = PortfolioStorage(data_dir=self.data_dir, filename=self.test_filename)
        flask_app.portfolio_storage = self.test_storage
        
        self.app = flask_app.app.test_client()
        self.app.testing = True
        
        # Clean start
        if os.path.exists(self.test_storage.filepath):
            os.remove(self.test_storage.filepath)
        
    def tearDown(self):
        # Restore actual storage
        flask_app.portfolio_storage = self.original_storage
        
        # Cleanup test file
        if os.path.exists(self.test_storage.filepath):
            os.remove(self.test_storage.filepath)

    def test_universe(self):
        response = self.app.get('/api/universe')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(isinstance(data, list))
        if len(data) > 0:
            print(f"Universe loaded with {len(data)} items.")
            self.assertIn('symbol', data[0])
            self.assertIn('data', data[0])

    def test_portfolio_flow(self):
        # 1. Initial Empty
        resp = self.app.get('/api/portfolio')
        data = json.loads(resp.data)
        # Check nested structure: accounts -> '기본 계좌' -> positions
        self.assertEqual(data.get('accounts')['기본 계좌'].get('positions'), {})

        # 2. Add Item
        resp = self.app.post('/api/portfolio', json={'symbol': '005930', 'qty': 10})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['accounts']['기본 계좌']['positions']['005930']['qty'], 10)
        
        # 3. Verify Persistence
        resp = self.app.get('/api/portfolio')
        data = json.loads(resp.data)
        self.assertEqual(data['accounts']['기본 계좌']['positions']['005930']['qty'], 10)

        # 4. Bulk Update
        bulk_data = {
            "positions": {
                "005930": 20,
                "069500": 5
            },
            "account": "기본 계좌"
        }
        resp = self.app.post('/api/portfolio/bulk', json=bulk_data)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['accounts']['기본 계좌']['positions']['005930']['qty'], 20)
        self.assertEqual(data['accounts']['기본 계좌']['positions']['069500']['qty'], 5)

        # 5. Delete Item (qty=0)
        resp = self.app.post('/api/portfolio', json={'symbol': '005930', 'qty': 0})
        data = json.loads(resp.data)
        self.assertNotIn('005930', data['accounts']['기본 계좌']['positions'])
        self.assertIn('069500', data['accounts']['기본 계좌']['positions'])

        # 6. Clear All
        resp = self.app.post('/api/portfolio/clear')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get('accounts')['기본 계좌'].get('positions'), {})

if __name__ == '__main__':
    unittest.main()
