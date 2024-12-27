from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
import dotenv
import os
import random
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
dotenv.load_dotenv(override=True)
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key')

def create_spotify_oauth():
    cache_handler = FlaskSessionCacheHandler(session)
    return SpotifyOAuth(
        client_id=os.getenv('client_id'),
        client_secret=os.getenv('client_secret'),
        redirect_uri=os.getenv('redirect_uri'),
        scope="user-top-read",
        cache_handler=cache_handler,
        show_dialog=False,
    )
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["240 per day", "60 per hour"]
)
def authenticate_user():
    spotify_oauth = create_spotify_oauth()
    auth_url = spotify_oauth.get_authorize_url()
    return auth_url

def get_all_albums():
    spotify_oauth = create_spotify_oauth()
    token_info = spotify_oauth.get_cached_token()
    if token_info:
        spotify = spotipy.Spotify(auth_manager=spotify_oauth)
        try:
            all_album_uris = []
            offset = 0
            while True:
                albums = spotify.artist_albums('1Cd373x8qzC7SNUg5IToqp', country='US', limit=50, offset=offset)
                if not albums['items']:
                    break
                else:
                    for album in albums['items']:
                        album_tracks = spotify.album_tracks(album['uri'])
                        if not len(album_tracks['items']) == 1 and not album_tracks['items'][0]['name'] == 'Gaslight':
                            all_album_uris.append(album['uri'])
                    offset += 50
            return all_album_uris
        except Exception as e:
            print(f"Error fetching albums: {e}")
            return None
    return None

def get_top_tracks():
    spotify_oauth = create_spotify_oauth()
    token_info = spotify_oauth.get_cached_token()
    if token_info:
        spotify = spotipy.Spotify(auth_manager=spotify_oauth)
        try:
            album_uris = get_all_albums()
            found_albums = set()
            top_tracks_data = []
            offset = 0
            
            while len(found_albums) < len(album_uris) and offset < 1000:
                results = spotify.current_user_top_tracks(limit=50, offset=offset, time_range='long_term')
                
                for track in results['items']:
                    album_uri = track['album']['uri']
                    if album_uri in album_uris and album_uri not in found_albums:
                        found_albums.add(album_uri)
                        track_data = {
                            'name': track['name'],
                            'cover_url': track['album']['images'][0]['url'],
                            'album_uri': album_uri,
                            'album_name': track['album']['name']
                        }
                        top_tracks_data.append(track_data)
                
                if not results['items']:
                    break
                    
                offset += 50
                
            return top_tracks_data
        except Exception as e:
            print(f"Error fetching tracks: {e}")
            return None
    return None

def get_random_cover(oauth):
    spotify = spotipy.Spotify(auth_manager=oauth)
    albums = spotify.artist_albums('1Cd373x8qzC7SNUg5IToqp')
    if not albums['items']:
        raise Exception("No albums found for the artist.")
    
    album_uris = [album['uri'] for album in albums['items']]
    random_album_uri = random.choice(album_uris)
    album = spotify.album(random_album_uri)
    return album['images'][0]['url']

@app.route('/')
def index():
    spotify_oauth = create_spotify_oauth()
    if spotify_oauth.get_cached_token():
        return redirect(url_for('top_tracks'))

    return render_template('index.html')

@app.route('/authenticate', methods=['POST'])
def authenticate():
    auth_link = authenticate_user()
    return redirect(auth_link)

@app.route('/top-tracks')
@limiter.limit("1/minute")
def top_tracks():
    spotify_oauth = create_spotify_oauth()
    if not spotify_oauth.get_cached_token():
        return redirect(url_for('index'))
    cover = get_random_cover(oauth=spotify_oauth)
    return render_template('top_tracks.html', random_album_cover=cover)

@app.route('/api/top-tracks')
def api_top_tracks():
    spotify_oauth = create_spotify_oauth()
    if not spotify_oauth.get_cached_token():
        return jsonify({'error': 'Not authenticated'}), 401
    tracks = get_top_tracks()
    if not tracks:
        return jsonify({'error': 'You have never listened to any songs from the artist'}), 404
    return jsonify({'tracks': tracks})


@app.route('/callback')
def callback():
    spotify_oauth = create_spotify_oauth()
    code = request.args.get('code')
    if code:
        try:
            spotify_oauth.get_access_token(code, as_dict=False)
            return redirect(url_for('top_tracks'))
        except Exception as e:
            print(f"Error in callback: {e}")
            return 'Authentication failed!', 400
    return 'Authentication failed!', 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host=os.getenv('host'))