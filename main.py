from __future__ import unicode_literals
import datetime
import os
import json
import logging
import requests
import sys
import youtube_dl

logger = logging.getLogger(__name__)
logging.basicConfig(filename='log.log', format='%(levelname)s - %(message)s', level=logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
logger.addHandler(ch)

CLIENT_ID = '2t9loNQH90kzJcsFCODdigxfp325aq4z'
REPEATABLE_PARAMS = '&app_version=1478268854&client_id=' + CLIENT_ID
SEED_URL = 'https://api-v2.soundcloud.com/users/{user_id}/likes?offset=0&limit=100'

def extract_user_id(user_page):
    """ forgive my lack of regex knowledge... """
    pre_id = 'https://api.soundcloud.com/users/'
    beginning_id = user_page.index(pre_id) + len(pre_id)
    end_id = beginning_id + user_page[beginning_id:].index('"')
    user_id = user_page[beginning_id:end_id]
    return user_id

def main(username):
    logger.info("Getting user ID for {}...".format(username))
    user_page = requests.get('https://soundcloud.com/{}'.format(username)).content.decode('utf-8')
    user_id = extract_user_id(user_page)

    logger.info("User ID is {}".format(user_id))
    logger.info("Loading urls of all previously downloaded songs...")
    downloaded = set()
    # don't download previously downloaded files
    if os.path.exists('./downloaded.txt'):
        with open('./downloaded.txt') as links:
            downloaded = set(links.read().splitlines())

    # don't download ignored files
    if os.path.exists('./ignored.txt'):
        with open('./ignored.txt') as ignored:
            ignored = set(ignored.read().splitlines())
            downloaded |= ignored

    logger.info("Loaded {} urls".format(len(downloaded)))
    logger.info("Retrieving all of {}'s SoundCloud likes...".format(username))
    to_download = []
    url = SEED_URL.format(user_id=user_id)
    while True:
        payload = json.loads(requests.get(url + REPEATABLE_PARAMS).content.decode('utf-8'))
        for like_json in payload['collection']:
            if 'track' in like_json:
                try:
                    permalink_url = like_json['track']['permalink_url']
                    if permalink_url not in downloaded:
                        to_download.append(permalink_url)
                except KeyError:
                    logger.error('The SoundCloud API threw us a curveball. The raw JSON for the unparseable text:\n{}'.format(
                        json.dumps(like_json)
                    ))
                    pass
        url = payload.get('next_href')
        if url is None:
            break

    if not to_download:
        logger.info("There are no new files to download")
    else:
        successful_urls = []
        unsuccessful_urls = []
        ydl_opts = {'outtmpl': './songs/%(uploader)s - %(title)s (%(id)s).%(ext)s'}
        for idx, permalink in enumerate(to_download, start=1):
            logger.info('Downloading {} of {} songs'.format(idx, len(to_download)))
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([permalink])
                    successful_urls.append(permalink)
                except Exception as e:
                    # first 18 chars are ERROR displayed in red
                    unsuccessful_urls.append((str(e)[18:], permalink))

        log_mode = 'a' if os.path.exists('./downloaded.txt') else 'w+'
        with open('./downloaded.txt', log_mode) as already_downloaded_log:
            for url in successful_urls:
                already_downloaded_log.write("{}\n".format(url))

        if unsuccessful_urls:
            errors_log_exists = os.path.exists('./errors.txt')
            errors_log_mode = 'a' if errors_log_exists else 'w+'
            with open('./errors.txt', errors_log_mode) as errors_log:
                errors_log.write('{linebreak}Errors on run: {timelog}\n'.format(
                    linebreak='\n\n' if errors_log_exists else '',
                    timelog=datetime.datetime.now().strftime('%m/%d/%Y @ %H:%M:%S'))
                )
                for error, url in unsuccessful_urls:
                    errors_log.write('{}\n{}\n\n'.format(error, url))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.error("You must enter your SoundCloud username, (EX: 'python main.py username')")
    else:
        main(sys.argv[1])
