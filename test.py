import unittest
from flask import request
from app import app, socketio, user_data


class ChatAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.socketio_test_client = socketio.test_client(app)

    # ------------------ ROUTE TESTS ------------------ ##
    def test_chat_page_loads(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Chat", response.data)  # Assuming title includes "Chat"

    def test_upload_file_no_file(self):
        response = self.app.post('/upload', data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error'], 'No file uploaded')

    # ------------------ SOCKET.IO TESTS ------------------ ##
    def test_validate_username(self):
        with app.test_request_context():
            request.remote_addr = '127.0.0.1'
            self.socketio_test_client.emit('validate_username', {'username': 'testuser'})
            received = self.socketio_test_client.get_received()

            self.assertEqual(received[0]['name'], 'username_validation')
            self.assertTrue(received[0]['args'][0]['is_valid'])
            self.assertEqual(received[0]['args'][0]['username'], 'testuser')

    def test_send_message_empty(self):
        with app.test_request_context():
            request.remote_addr = '127.0.0.1'
            user_data['127.0.0.1'] = 'testuser'

            self.socketio_test_client.emit('send_message', {'message': ''})

            received = self.socketio_test_client.get_received()

            # Assert that we received a message with empty text
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]['name'], 'new_message')
            self.assertEqual(received[0]['args'][0]['text'], '')

    def test_send_file_no_filename(self):
        with app.test_request_context():
            request.remote_addr = '127.0.0.1'
            user_data['127.0.0.1'] = 'testuser'

            test_data = {
                'filename': '',
                'url': '/uploads/example.png'
            }
            self.socketio_test_client.emit('send_file', test_data)
            received = self.socketio_test_client.get_received()
            self.assertEqual(received[0]['args'][0]['filename'], '')

    # ------------------ CLEANUP ------------------ ##
    def tearDown(self):
        user_data.clear()


if __name__ == '__main__':
    unittest.main()
