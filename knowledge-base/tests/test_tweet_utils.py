import unittest
from pathlib import Path
from knowledge_base_agent.tweet_utils import parse_tweet_id_from_url, load_tweet_urls_from_links

class TestTweetUtils(unittest.TestCase):
    def test_parse_tweet_id_from_url(self):
        url = "https://twitter.com/user/status/1234567890"
        tweet_id = parse_tweet_id_from_url(url)
        self.assertEqual(tweet_id, "1234567890")

    def test_load_tweet_urls_from_links(self):
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile("w+", delete=False) as tmp:
            tmp.write("https://twitter.com/user/status/111111\n")
            tmp.write("https://twitter.com/user/status/222222\n")
            tmp_filename = tmp.name
        urls = load_tweet_urls_from_links(Path(tmp_filename))
        self.assertEqual(len(urls), 2)

if __name__ == '__main__':
    unittest.main()
