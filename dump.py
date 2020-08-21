import argparse
import asyncio
import json
import logging
import zipfile

import aiohttp, requests

discord_api = "https://discord.com/api/v8/{}"
discord_cdn = "https://cdn.discordapp.com/{}"

user_agent = 'Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 ' \
             '(KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36'

# converts spaces into underscores and removes illegal chars from string
illegals = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
sanitize = lambda string: ''.join(char for char in string.replace(' ', '_') if char not in illegals)


def print_guilds(guild_list):
    for index in range(len(guild_list)):
        print(f'[{index + 1:02d}] {guild_list[index]["name"]}')

    print('-' * 50)


def main():
    user_guilds = load_guilds()
    user_guilds.sort(key=lambda g: g['name'])  # sort guilds alphabetically
    print_guilds(user_guilds)

    while True:
        try:
            print('\n[A] Dump emotes from all guilds\n[R] Print guild list\n[Q] Quit\n')
            index = input('Guild Index > ').lower()

            if index == 'a':
                # TODO: Make this faster
                # TODO: Show how many emotes were downloaded in total
                # TODO: Show how long it took?
                logging.info('Dumping from all guilds... (This may take a while)')

                for guild in user_guilds:
                    dump_emotes(guild['id'])

            if index == 'r':
                print_guilds(user_guilds)
            if index == 'q':
                raise KeyboardInterrupt
            else:
                try:
                    selection = int(index) - 1
                    if selection > len(user_guilds):
                        pass
                    else:
                        dump_emotes(user_guilds[selection]['id'])
                except ValueError:
                    pass

        except KeyboardInterrupt:
            print('\nGoodbye! (^_^)／')
            quit()


def load_guilds():
    route = 'users/@me/guilds'
    res = requests.get(discord_api.format(route), headers={'Authorization': token, 'User-Agent': user_agent})

    if res.status_code == 401:
        logging.info('Failed to load user guilds, unauthorized')
        exit()
    if res.status_code == 200:
        return res.json()


def dump_emotes(guild_id):
    route = f'guilds/{guild_id}'
    res = requests.get(discord_api.format(route), headers={'Authorization': token, 'User-Agent': user_agent})

    if res.status_code != 200:
        logging.info(f'Failed to dump guild emotes, unknown guild')

    else:
        guild_name = sanitize(res.json()['name'])

        if args.json:
            logging.info(f'Dumping guild info into {guild_name}.json')
            with open(f'{guild_name}.json', 'w') as dump:
                dump.write(json.dumps(res.json(), indent=4))

        else:
            emote_list = res.json()['emojis']
            logging.info(f'Dumping {len(emote_list)} emotes... from {res.json()["name"]}')

            task_list = [asyncio.ensure_future(download_emote(emote)) for emote in emote_list]
            loop = asyncio.get_event_loop()

            results = loop.run_until_complete(asyncio.gather(*task_list))

            create_archive(guild_name, results)
            logging.info('Done.')


def create_archive(zip_name, data):
    logging.info(f'Adding emotes to Emotes_{zip_name}.zip')

    with zipfile.ZipFile(f'Emotes_{zip_name}.zip', 'w', zipfile.ZIP_STORED) as z:
        duplicates = []

        for emote in data:
            extension = emote["extension"]
            filename = emote["name"]+extension

            if filename in z.namelist() or f'animated/{filename}' in z.namelist():
                appears = duplicates.count(filename)
                duplicates.append(filename)

                filename = f'{filename[:-len(extension)]}~{appears+1}{extension}'
                logging.debug(f'Duplicate Detected, new filename:{filename}')

            if extension == '.gif':
                z.writestr(f'animated/{filename}', emote["data"])
            else:
                z.writestr(filename, emote["data"])


async def download_emote(emote):
    extension = '.gif' if emote['animated'] else '.png'
    route = f'emojis/{emote["id"]}{extension}'

    async with aiohttp.ClientSession(headers={'User-Agent': user_agent}) as session:
        async with session.get(discord_cdn.format(route)) as res:
            if res.status == 200:
                return {
                    "name": emote['name'],
                    "id": emote['id'],
                    "extension": extension,
                    "data": await res.content.read()}
            else:
                logging.debug(f'Failed to download emote:id:{emote["id"]} from\n{res.url}')


def load_token():
    try:
        with open('settings.json') as s:
            settings = json.load(s)

        if settings['token'] == "":
            logging.warning("Blank token detected in settings")
            exit()

        return settings['token']

    except FileNotFoundError:
        logging.error('Could not locate settings file. Make sure it is in the same directory ')
        exit()


if __name__ == '__main__':
    # set logging level to logging.DEBUG to see HTTP(s) requests
    logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s',
                        datefmt='%H:%M:%S',
                        level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--token',
                        metavar="TOKEN",
                        help='Use specified token instead loading from settings',
                        action='store')

    parser.add_argument('--dir',
                        metavar='DIRECTORY',
                        help='Directory where files should be created',
                        action='store')

    parser.add_argument('--guild',
                        metavar="ID",
                        help='Dump emotes from specified guild',
                        action='store')

    parser.add_argument('--json',
                        help='Dump guild info into a json file instead of creating an archive',
                        action="store_true")

    args = parser.parse_args()
    if args.token:
        token = args.token
    else:
        token = load_token()

    if args.dir:
        import os
        if os.path.isdir(args.dir):
            logging.debug(f'Changing cwd to {args.dir}')
            os.chdir(args.dir)
        else:
            logging.debug(f'Creating dir at {args.dir} and changing cwd')
            os.mkdir(args.dir)
            os.chdir(args.dir)

    if args.guild:
        dump_emotes(args.guild)
        quit()

    main()
