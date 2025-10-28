# -*- coding: utf-8 -*-

### Imports ###
import sys                  # getdefaultencoding, getfilesystemencoding, platform, argv
import os                   # path.abspath, join, dirname
import re                   #
import inspect              # getfile, currentframe
import urllib2              #
from   lxml    import etree #
from   io      import open  # open
import hashlib
import glob                 # HINZUGEFÜGT: Für optimierte Dateisuche
import time                 # HINZUGEFÜGT: Für Performance-Messung
import json                 # HINZUGEFÜGT: Für verbesserte JSON-Behandlung
import unicodedata          # HINZUGEFÜGT: Für Unicode-Normalisierung

###Mini Functions ###
def natural_sort_key     (s):  return [int(text) if text.isdigit() else text for text in re.split(re.compile('([0-9]+)'), str(s).lower())]  ### Avoid 1, 10, 2, 20... #Usage: list.sort(key=natural_sort_key), sorted(list, key=natural_sort_key)
def sanitize_path        (p):  return "" if p is None else (p if isinstance(p, unicode) else p.decode(sys.getfilesystemencoding())) ### Make sure the path is unicode, if it is not, decode using OS filesystem's encoding ###
def js_int               (i):  return int(''.join([x for x in list(i or '0') if x.isdigit()]))  # js-like parseInt - https://gist.github.com/douglasmiranda/2174255

### XML-SAFE SANITIZER - VERBESSERTE VERSION ###
RE_XML_FORBIDDEN = re.compile(
    u'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u200B-\u200D\u2060\uFEFF\uFFF9-\uFFFC\uFFFE\uFFFF]'
)

def xml_safe(s):
    """Macht Strings XML-kompatibel durch Entfernung von Null-Bytes, Steuerzeichen und Zero-Width-Zeichen"""
    if s is None:
        return u''
    if not isinstance(s, unicode):
        try:
            s = s.decode('utf-8', 'replace')
        except:
            try:
                s = unicode(str(s), errors='replace')
            except:
                return u''
    
    # Unicode normalisieren (z.B. seltsame Kombinatoren)
    try:
        s = unicodedata.normalize('NFC', s)
    except:
        pass
    
    # alle problematischen Steuer-/Zero-Width-Zeichen raus
    s = RE_XML_FORBIDDEN.sub(u'', s)
    
    # Zusätzlich: Entferne andere problematische Zeichen
    s = s.replace('\x00', '').replace('\ufeff', '').replace('\ufffd', '')
    
    # Entferne oder ersetze Zeichen, die in Dateipfaden problematisch sein könnten
    s = re.sub(r'[<>:"/\\|?*]', '_', s)
    
    return s.strip()

def safe_id_component(s):
    """Erstellt sichere ID-Komponenten für GUIDs"""
    if s is None:
        return 'unknown'
    s = xml_safe(s)
    # Entferne alle nicht-alphanumerischen Zeichen außer ._-
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s)
    # Entferne führende/trailing Underscores und begrenze Länge
    s = s.strip('_')[:120]
    return s if s else 'unknown'

def create_youtube_guid(guid_type, youtube_id, folder_component):
    """Erstellt strukturierte YouTube GUIDs mit korrekten Präfixen"""
    safe_youtube_id = safe_id_component(youtube_id) if youtube_id else 'unknown'
    safe_folder = safe_id_component(folder_component) if folder_component else 'unknown'
    
    # Verwende Präfixe für bessere Unterscheidung
    if guid_type == 'channel':
        return u'youtube|ch:{}|{}'.format(safe_youtube_id, safe_folder)
    elif guid_type == 'playlist':
        return u'youtube|pl:{}|{}'.format(safe_youtube_id, safe_folder)
    elif guid_type == 'video':
        return u'youtube|v:{}|{}'.format(safe_youtube_id, safe_folder)
    else:
        return u'youtube|{}|{}'.format(safe_youtube_id, safe_folder)

### Return dict value if all fields exists "" otherwise (to allow .isdigit()), avoid key errors
def Dict(var, *arg, **kwarg):  #Avoid TypeError: argument of type 'NoneType' is not iterable
  """ Return the value of an (imbricated) dictionnary, return "" if doesn't exist unless "default=new_value" specified as end argument
      Ex: Dict(variable_dict, 'field1', 'field2', default = 0)
  """
  for key in arg:
    if isinstance(var, dict) and key and key in var or isinstance(var, list) and isinstance(key, int) and 0<=key<len(var):  var = var[key]
    else:  return kwarg['default'] if kwarg and 'default' in kwarg else ""   # Allow Dict(var, tvdbid).isdigit() for example
  return kwarg['default'] if var in (None, '', 'N/A', 'null') and kwarg and 'default' in kwarg else "" if var in (None, '', 'N/A', 'null') else var

### Used to Convert Crowd Sourced Video Titles to Title Case from Sentence Case
def uppercase_regex(a):
    return a.group(1) + a.group(2).upper()

def titlecase(input_string):
    return re.sub("(^|\s)(\S)", uppercase_regex, input_string)

### These calls use DeArrow Created By Ajay Ramachandran to Obtain a Crowd Sourced Video Title
def DeArrow(video_id):
  api_url = 'https://sponsor.ajay.app'

  hash = hashlib.sha256(video_id.encode('ascii')).hexdigest()
  
  # DeArrow API recommends using first 4 hash characters.
  url = '{api_url}/api/branding/{hash}'.format(api_url = api_url, hash = hash[:4])

  #HTTP.ClearCache()
  HTTP.CacheTime = 0

  crowd_sourced_title = ''
  
  try:
    data_json = JSON.ObjectFromURL(url)
  except:
    Log.Error(u'DeArrow(): Error while loading JSON.ObjectFromURL. URL: '+ url)

  try:
    first_title_obj = data_json[video_id]['titles'][0]
    if (first_title_obj['votes'] >= 0 and first_title_obj['locked'] == False and first_title_obj['original'] == False):
      crowd_sourced_title = xml_safe(titlecase(first_title_obj['title']))  # XML-SAFE
  except:
    Log.Info(u'DeArrow(): No Crowd Sourced Title Found for Video ID: ' + video_id)

  HTTP.CacheTime = CACHE_1MONTH
  
  return crowd_sourced_title

### Convert ISO8601 Duration format into seconds ###
def ISO8601DurationToSeconds(duration):
  try:     match = re.match('PT(\d+H)?(\d+M)?(\d+S)?', duration).groups()
  except:  return 0
  else:    return 3600 * js_int(match[0]) + 60 * js_int(match[1]) + js_int(match[2])

### Get media directory ###
def GetMediaDir (media, movie, file=False):
  if movie:  return os.path.dirname(media.items[0].parts[0].file)
  else:
    for s in media.seasons if media else []: # TV_Show:
      for e in media.seasons[s].episodes:
        Log.Info(media.seasons[s].episodes[e].items[0].parts[0].file)
        return media.seasons[s].episodes[e].items[0].parts[0].file if file else os.path.dirname(media.seasons[s].episodes[e].items[0].parts[0].file)

### Get media root folder ###
def GetLibraryRootPath(dir):
  library, root, path = '', '', ''
  for root in [os.sep.join(dir.split(os.sep)[0:x+2]) for x in range(0, dir.count(os.sep))]:
    if root in PLEX_LIBRARY:
      library = PLEX_LIBRARY[root]
      path    = os.path.relpath(dir, root)
      break
  else:  #401 no right to list libraries (windows)
    Log.Info(u'[!] Library access denied')
    filename = os.path.join(CachePath, '_Logs', '_root_.scanner.log')
    if os.path.isfile(filename):
      Log.Info(u'[!] ASS root scanner file present: "{}"'.format(filename))
      line = Core.storage.load(filename)  #with open(filename, 'rb') as file:  line=file.read()
      for root in [os.sep.join(dir.split(os.sep)[0:x+2]) for x in range(dir.count(os.sep)-1, -1, -1)]:
        if "root: '{}'".format(root) in line:  path = os.path.relpath(dir, root).rstrip('.');  break  #Log.Info(u'[!] root not found: "{}"'.format(root))
      else: path, root = '_unknown_folder', ''
    else:  Log.Info(u'[!] ASS root scanner file missing: "{}"'.format(filename))
  return library, root, path


def youtube_api_key():
  path = os.path.join(PluginDir, "youtube-key.txt")
  if os.path.isfile(path):
    value = Data.Load(path)
    if value:
      value = value.strip()
    if value:
      Log.Debug(u"Loaded token from youtube-token.txt file")

      return value

  # Fall back to Library preference
  return Prefs['YouTube-Agent_youtube_api_key']

### NEUE VERBESSERUNGEN ###

# Error Tracking für bessere Diagnostik
ERROR_COUNTS = {}

def track_error(error_type, details):
    """Verfolge Fehler für bessere Diagnostik"""
    global ERROR_COUNTS
    if error_type not in ERROR_COUNTS:
        ERROR_COUNTS[error_type] = []
    ERROR_COUNTS[error_type].append(details)
    
    # Log Zusammenfassung alle 10 Fehler
    if len(ERROR_COUNTS[error_type]) % 10 == 0:
        Log.Warn(u"Error type '{}' occurred {} times".format(error_type, len(ERROR_COUNTS[error_type])))

def clean_json_content(content):
    """Bereinige häufige JSON-Formatierungsprobleme"""
    # Entferne UTF-8 BOM falls vorhanden
    if content.startswith('\ufeff'):
        content = content[1:]
    
    # Entferne trailing commas vor schließenden Klammern
    content = re.sub(r',(\s*[}\]])', r'\1', content)
    
    # Entferne single-line comments (basic)
    content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
    
    # Entferne multi-line comments (basic)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    return content.strip()

def extract_essential_data(json_file_path):
    """Letzte Rettung: extrahiere wichtige Video-Daten mit Regex wenn JSON parsing fehlschlägt"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extrahiere wichtige Felder mit Regex
        video_id_match = re.search(r'"id":\s*"([^"]+)"', content)
        title_match = re.search(r'"title":\s*"([^"]+)"', content)
        uploader_match = re.search(r'"uploader":\s*"([^"]+)"', content)
        duration_match = re.search(r'"duration":\s*(\d+)', content)
        
        if video_id_match:
            essential_data = {
                'id': video_id_match.group(1),
                'title': xml_safe(title_match.group(1)) if title_match else 'Unknown Title',  # XML-SAFE
                'uploader': xml_safe(uploader_match.group(1)) if uploader_match else 'Unknown Uploader',  # XML-SAFE
                'duration': int(duration_match.group(1)) if duration_match else 0,
                'description': 'Data recovered from corrupted JSON file'
            }
            Log.Info(u'Essential data extracted from corrupted JSON: {}'.format(essential_data['id']))
            return essential_data
        else:
            Log.Error(u'Could not extract video ID from corrupted JSON: {}'.format(json_file_path))
            return None
            
    except Exception as e:
        Log.Error(u'Failed to extract essential data from {}: {}'.format(json_file_path, str(e)))
        track_error('json_extraction_failed', str(e))
        return None

###
def json_load(template, *args):
  url = template.format(*args + tuple([youtube_api_key()]))
  url = sanitize_path(url)
  iteration = 0
  json_page = {}
  json      = {}
  while not json or Dict(json_page, 'nextPageToken') and Dict(json_page, 'pageInfo', 'resultsPerPage') !=1 and iteration<50:
    #Log.Info(u'{}'.format(Dict(json_page, 'pageInfo', 'resultsPerPage')))
    try:                    json_page = JSON.ObjectFromURL(url+'&pageToken='+Dict(json_page, 'nextPageToken') if Dict(json_page, 'nextPageToken') else url)  #Log.Info(u'items: {}'.format(len(Dict(json_page, 'items'))))
    except Exception as e:  
        track_error('api_call_failed', str(e))
        json = JSON.ObjectFromString(e.content);  raise ValueError('code: {}, message: {}'.format(Dict(json, 'error', 'code'), Dict(json, 'error', 'message')))
    if json:  json ['items'].extend(json_page['items'])
    else:     json = json_page
    iteration +=1
  #Log.Info(u'total items: {}'.format(len(Dict(json, 'items'))))
  return json

### OPTIMIERT: Cache für JSON-Dateien (ohne Unterstrich für RestrictedPython)
JSON_FILE_CACHE = {}

### API-Response Cache für Performance-Optimierung
API_RESPONSE_CACHE = {}
API_CACHE_TTL = 3600  # 1 Stunde in Sekunden

def json_load_cached(template, *args, **kwargs):
  """
  Gecachte Version von json_load() für API-Responses
  - Cache-TTL: 1 Stunde (3600 Sekunden)
  - Reduziert redundante API-Calls bei Updates
  - force_refresh=True überspringt Cache
  """
  import time

  force_refresh = kwargs.get('force_refresh', False)
  cache_key = template.format(*args + tuple(['CACHE_KEY']))
  current_time = time.time()

  # Cache prüfen (wenn nicht force_refresh)
  if not force_refresh and cache_key in API_RESPONSE_CACHE:
    cached_entry = API_RESPONSE_CACHE[cache_key]
    cache_age = current_time - cached_entry['timestamp']

    if cache_age < API_CACHE_TTL:
      Log.Info(u'[CACHE HIT] Using cached API response (age: {:.0f}s)'.format(cache_age))
      return cached_entry['data']
    else:
      Log.Info(u'[CACHE EXPIRED] Cache too old ({:.0f}s), refreshing...'.format(cache_age))

  # Cache-Miss oder abgelaufen: Fresh API-Call
  Log.Info(u'[CACHE MISS] Loading fresh API data...')
  try:
    data = json_load(template, *args)

    # In Cache speichern
    API_RESPONSE_CACHE[cache_key] = {
      'data': data,
      'timestamp': current_time
    }

    Log.Info(u'[CACHE STORED] API response cached for future use')
    return data

  except Exception as e:
    Log.Error(u'[CACHE ERROR] API call failed: {}'.format(str(e)))
    raise

def cleanup_api_cache():
  """
  Entfernt abgelaufene Cache-Einträge (älter als 2 Stunden)
  """
  import time
  current_time = time.time()
  expired_keys = []

  for key, entry in API_RESPONSE_CACHE.items():
    cache_age = current_time - entry['timestamp']
    if cache_age > (API_CACHE_TTL * 2):  # 2 Stunden
      expired_keys.append(key)

  for key in expired_keys:
    del API_RESPONSE_CACHE[key]

  if expired_keys:
    Log.Info(u'[CACHE CLEANUP] Removed {} expired entries, {} active'.format(len(expired_keys), len(API_RESPONSE_CACHE)))

### VERBESSERTE JSON-Datei laden mit umfassender Fehlerbehandlung
def load_json_file_safe(json_file_path):
    """
    Verbesserte JSON-Laden mit umfassender Fehlerbehandlung und Fallback-Parsing
    """
    if not os.path.exists(json_file_path):
        Log.Debug(u'JSON file does not exist: {}'.format(json_file_path))
        return None
    
    try:
        # Methode 1: Versuche Plex's JSON loader zuerst
        json_video_details = JSON.ObjectFromString(Core.storage.load(json_file_path))
        if json_video_details and Dict(json_video_details, 'id'):
            Log.Debug(u'JSON successfully loaded via Plex: Video-ID {}'.format(Dict(json_video_details, 'id')))
            return json_video_details
        else:
            Log.Warn(u'JSON loaded but missing video ID: {}'.format(json_file_path))
            return None
            
    except Exception as plex_error:
        Log.Debug(u'Plex JSON loader failed: {}, trying standard JSON'.format(str(plex_error)))
        track_error('plex_json_failed', str(plex_error))
        
        try:
            # Methode 2: Fallback zu standard JSON parsing
            with open(json_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Bereinige häufige Probleme vor dem Parsing
            content = clean_json_content(content)
            json_video_details = json.loads(content)
            
            if json_video_details and json_video_details.get('id'):
                Log.Info(u'JSON recovered via standard parser: Video-ID {}'.format(json_video_details.get('id')))
                return json_video_details
            else:
                Log.Warn(u'JSON recovered but missing video ID: {}'.format(json_file_path))
                return None
                
        except Exception as std_error:
            Log.Error(u'All JSON parsing failed for {}: Plex={}, Std={}'.format(
                json_file_path, str(plex_error), str(std_error)))
            track_error('standard_json_failed', str(std_error))
            
            # Methode 3: Letzter Ausweg - versuche wichtige Daten manuell zu extrahieren
            return extract_essential_data(json_file_path)

def build_json_cache(series_root_folder):
    """Erstelle JSON-Datei Cache mit besserer Fehlerbehandlung"""
    cache_start = time.time()
    cache_key = series_root_folder
    
    JSON_FILE_CACHE[cache_key] = {}
    json_count = 0
    
    try:
        for root, dirs, files in os.walk(series_root_folder):
            # Überspringe versteckte Verzeichnisse und häufige Nicht-Media-Ordner
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ['@eadir', 'thumbs']]
            
            for f in files:
                if f.endswith(".info.json"):
                    json_path = os.path.join(root, f)
                    JSON_FILE_CACHE[cache_key][f] = json_path
                    json_count += 1
        
        cache_time = time.time() - cache_start
        Log.Info(u'JSON cache built ({:.3f}s): {} files indexed'.format(cache_time, json_count))
        
    except Exception as e:
        Log.Error(u'Error building JSON cache for {}: {}'.format(series_root_folder, str(e)))
        track_error('cache_build_failed', str(e))
        JSON_FILE_CACHE[cache_key] = {}

def cleanup_json_cache():
    """Bereinige alte Cache-Einträge um Speicherprobleme zu verhindern"""
    global JSON_FILE_CACHE
    if len(JSON_FILE_CACHE) > 50:  # Willkürliches Limit
        # Behalte nur die 30 zuletzt verwendeten Einträge
        sorted_cache = sorted(JSON_FILE_CACHE.items(), key=lambda x: len(x[1]), reverse=True)
        JSON_FILE_CACHE = dict(sorted_cache[:30])
        Log.Info(u'JSON cache cleaned up, kept 30 most recent entries')

### OPTIMIERT: Verbesserte JSON-Datei-Suche
def populate_episode_metadata_from_info_json_optimized(series_root_folder, filename):
    """
    Verbesserte JSON-Datei-Entdeckung mit verbessertem Caching und Fehlerbehandlung
    """
    start_time = time.time()
    json_filename = filename.rsplit('.', 1)[0] + ".info.json"
    
    # 1. ERSTE PRIORITÄT: Direkte Pfad-Prüfung
    direct_path = os.path.join(series_root_folder, json_filename)
    if os.path.exists(direct_path):
        search_time = time.time() - start_time
        Log.Info(u'info.json found directly ({:.3f}s): {}'.format(search_time, os.path.basename(direct_path)))
        return load_json_file_safe(direct_path)
    
    # 2. CACHE: Prüfe ob wir bereits alle JSON-Dateien für diesen Ordner gecacht haben
    cache_key = series_root_folder
    if cache_key not in JSON_FILE_CACHE:
        Log.Info(u'Building JSON cache for: {}'.format(os.path.basename(series_root_folder)))
        build_json_cache(series_root_folder)
    
    json_cache = JSON_FILE_CACHE.get(cache_key, {})
    
    # 3. ZWEITE PRIORITÄT: Exakte Dateinamen-Übereinstimmung im Cache
    if json_filename in json_cache:
        json_path = json_cache[json_filename]
        search_time = time.time() - start_time
        Log.Info(u'info.json found in cache ({:.3f}s): {}'.format(search_time, os.path.basename(json_path)))
        return load_json_file_safe(json_path)
    
    # 4. DRITTE PRIORITÄT: Video-ID Suche
    video_id_match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', filename)
    if video_id_match:
        video_id = video_id_match.group(1)
        Log.Debug(u'Searching by video ID: {}'.format(video_id))
        
        for cached_filename, cached_path in json_cache.items():
            if video_id in cached_filename:
                search_time = time.time() - start_time
                Log.Info(u'info.json found by video ID ({:.3f}s): {}'.format(search_time, os.path.basename(cached_path)))
                return load_json_file_safe(cached_path)
    
    search_time = time.time() - start_time
    Log.Debug(u'No info.json found ({:.3f}s): {}'.format(search_time, json_filename))
    return None

### load image if present in local dir
def img_load(series_root_folder, filename):
  Log(u'img_load() - series_root_folder: {}, filename: {}'.format(series_root_folder, filename))
  for ext in ['jpg', 'jpeg', 'png', 'tiff', 'gif', 'jp2']:
    filename = os.path.join(series_root_folder, filename.rsplit('.', 1)[0]+"."+ext)
    if os.path.isfile(filename):  Log(u'local thumbnail found for file %s', filename);  return filename, Core.storage.load(filename)
  return "", None

### get biggest thumbnail available
def get_thumb(json_video_details):
  thumbnails = Dict(json_video_details, 'thumbnails')
  for thumbnail in reversed(thumbnails):
    return thumbnail['url']

  Log.Error(u'get_thumb(): No thumb found')
  return None

def Start():
  HTTP.CacheTime                  = CACHE_1MONTH
  HTTP.Headers['User-Agent'     ] = 'Mozilla/5.0 (iPad; CPU OS 7_0_4 like Mac OS X) AppleWebKit/537.51.1 (KHTML, like Gecko) Version/7.0 Mobile/11B554a Safari/9537.54'
  HTTP.Headers['Accept-Language'] = 'en-us'

### Assign unique ID ###
def Search(results, media, lang, manual, movie):
  
  displayname = sanitize_path(os.path.basename((media.name if movie else media.show) or "") )
  filename    = media.items[0].parts[0].file if movie else media.filename or media.show
  dir         = GetMediaDir(media, movie)
  try:                    filename = sanitize_path(filename)
  except Exception as e:  Log('search() - Exception1: filename: "{}", e: "{}"'.format(filename, e))
  try:                    filename = os.path.basename(filename)
  except Exception as e:  Log('search() - Exception2: filename: "{}", e: "{}"'.format(filename, e))
  try:                    filename = urllib2.unquote(filename)
  except Exception as e:  Log('search() - Exception3: filename: "{}", e: "{}"'.format(filename, e))
  Log(u''.ljust(157, '='))
  Log(u"Search() - dir: {}, filename: {}, displayname: {}".format(dir, filename, displayname))
  
  ### TRY LOADING LOCAL JSON FILE FIRST - HIGHEST PRIORITY! ###
  json_filename = os.path.join(dir, os.path.splitext(filename)[0]+ ".info.json")
  Log(u'Searching for info file FIRST: {}'.format(json_filename))
  if os.path.exists(json_filename):
    try:     
      json_video_details = JSON.ObjectFromString(Core.storage.load(json_filename))
    except Exception as e:
      Log('search() - Unable to load info.json, e: "{}"'.format(e))
      track_error('search_json_failed', str(e))
    else:
      video_id = Dict(json_video_details, 'id')
      if video_id:  # Nur wenn Video-ID vorhanden
        Log('search() - SUCCESS: Loaded from .info.json: {}'.format(video_id))
        # KRITISCHER FIX: Für Movie verwende Video-GUID, für TV Show verwende Channel-GUID falls vorhanden
        if movie:
          safe_guid = create_youtube_guid('video', video_id, os.path.basename(dir))
        else:
          # Prüfe ob Channel-ID verfügbar ist
          channel_id = Dict(json_video_details, 'channel_id') or Dict(json_video_details, 'uploader_id')
          if channel_id and channel_id.startswith('UC'):
            safe_guid = create_youtube_guid('channel', channel_id, os.path.basename(dir))
          else:
            safe_guid = create_youtube_guid('video', video_id, os.path.basename(dir))
        
        safe_displayname = xml_safe(displayname)
        upload_date = Dict(json_video_details, 'upload_date')
        year = None
        if upload_date:
          try:
            parsed_date = Datetime.ParseDate(upload_date)
            if parsed_date:
              year = parsed_date.year
          except:
            pass
        
        results.Append( MetadataSearchResult( 
          id=safe_guid, 
          name=safe_displayname, 
          year=year, 
          score=100, 
          lang=lang 
        ))
        Log(u''.ljust(157, '='))
        return
    
  try:
    # 1. Suche zuerst im Ordnernamen (für Channel-IDs und Playlist-IDs)
    dir_basename = os.path.basename(dir)
    
    # Priorisiere Channel-IDs
    channel_match = re.search(r'\[([UC][a-zA-Z0-9\-_]{22})\]', dir_basename)
    if channel_match:
      channel_id = channel_match.group(1)
      clean_name = re.sub(r'\[[UC][a-zA-Z0-9\-_]{22,23}\]', '', dir_basename).strip()
      Log.Info(u'search() - Channel ID found in folder: "{}", clean name: "{}"'.format(channel_id, clean_name))
      safe_guid = create_youtube_guid('channel', channel_id, dir_basename)
      safe_clean_name = xml_safe(clean_name or displayname)
      results.Append( MetadataSearchResult( 
        id=safe_guid, 
        name=safe_clean_name, 
        year=None, score=100, lang=lang 
      ))
      Log(u''.ljust(157, '='))
      return
    
    # Dann Playlist-IDs
    playlist_match = re.search(r'\[(PL[a-zA-Z0-9\-_]{16,32}|UU[a-zA-Z0-9\-_]{22}|FL[a-zA-Z0-9\-_]{22}|LP[a-zA-Z0-9\-_]{22}|RD[a-zA-Z0-9\-_]{22})\]', dir_basename)
    if playlist_match:
      playlist_id = playlist_match.group(1)
      clean_name = re.sub(r'\[[PL][a-zA-Z0-9\-_]{16,32}\]|\[[UFL][UL][a-zA-Z0-9\-_]{22}\]|\[RD[a-zA-Z0-9\-_]{22}\]', '', dir_basename).strip()
      Log.Info(u'search() - Playlist ID found in folder: "{}", clean name: "{}"'.format(playlist_id, clean_name))
      safe_guid = create_youtube_guid('playlist', playlist_id, dir_basename)
      safe_clean_name = xml_safe(clean_name or displayname)
      results.Append( MetadataSearchResult( 
        id=safe_guid, 
        name=safe_clean_name, 
        year=None, score=100, lang=lang 
      ))
      Log(u''.ljust(157, '='))
      return
        
  except Exception as e:  
    Log('search() - Error searching for YouTube ID, error: "{}"'.format(e))
    track_error('search_regex_failed', str(e))
  
  # 2. Fallback: Suche im Dateinamen (für Video-IDs, nur für Movies oder als letzter Ausweg)
  if movie:
    try:
      video_match = re.search(r'\[([a-zA-Z0-9\-_]{11})\]', filename)
      if video_match:
        video_id = video_match.group(1)
        Log.Info(u'search() - Video ID found in filename: "{}"'.format(video_id))
        safe_guid = create_youtube_guid('video', video_id, os.path.basename(dir))
        safe_displayname = xml_safe(displayname)
        results.Append( MetadataSearchResult( 
          id=safe_guid, 
          name=safe_displayname, 
          year=None, score=90, lang=lang 
        ))
        Log(u''.ljust(157, '='))
        return
    except Exception as e:  
      Log('search() - Video ID search failed: "{}"'.format(e))
      track_error('video_id_search_failed', str(e))
  
  ### FALLBACK FOR S1_FORMAT ###
  try:
    s1_pattern = Regex('S1_.*?_(?:\d+p_)?\[(?P<id>[a-zA-Z0-9\-_]{11})\]', Regex.IGNORECASE)
    result = s1_pattern.search(filename)
    if result:
      video_id = result.group('id')
      Log.Info(u'search() - S1 Format Video ID found: "{}"'.format(video_id))
      # Für TV Shows, verwende Video-ID nur als Fallback
      safe_guid = create_youtube_guid('video', video_id, os.path.basename(dir))
      safe_displayname = xml_safe(displayname)
      results.Append( MetadataSearchResult( 
        id=safe_guid, 
        name=safe_displayname, 
        year=None, 
        score=85,  # Niedrigere Priorität
        lang=lang 
      ))
      Log(u''.ljust(157, '='))
      return
  except Exception as e:  
    Log('search() - S1 pattern failed: "{}"'.format(e))
    track_error('s1_pattern_failed', str(e))
  
  # ZUSÄTZLICHER FALLBACK: Video-ID am Ende des Dateinamens (ohne Klammern)
  try:
    filename_pattern = re.search(r'[_\s]([A-Za-z0-9_-]{11})(?=\.\w+$)', filename)
    if filename_pattern:
      video_id = filename_pattern.group(1)
      Log.Info(u'search() - Video ID found at filename end: "{}"'.format(video_id))
      safe_guid = create_youtube_guid('video', video_id, os.path.basename(dir))
      safe_displayname = xml_safe(displayname)
      results.Append( MetadataSearchResult( 
        id=safe_guid, 
        name=safe_displayname, 
        year=None, 
        score=80,  # Niedrigere Priorität
        lang=lang 
      ))
      Log(u''.ljust(157, '='))
      return
  except Exception as e:  
    Log('search() - Filename end pattern failed: "{}"'.format(e))
    track_error('filename_end_pattern_failed', str(e))
  
  if movie:  Log.Info(filename)
  else:    
    s = media.seasons.keys()[0] if media.seasons.keys()[0]!='0' else media.seasons.keys()[1] if len(media.seasons.keys()) >1 else None
    if s:
      result = YOUTUBE_PLAYLIST_REGEX.search(os.path.basename(os.path.dirname(dir)))
      guid   = result.group('id') if result else ''
      if result or os.path.exists(os.path.join(dir, 'youtube.id')):
        Log(u'search() - filename: "{}", found season YouTube playlist id, result.group("id"): {}'.format(filename, result.group('id')))
        safe_guid = create_youtube_guid('playlist', guid, dir)
        safe_filename = xml_safe(filename)
        results.Append( MetadataSearchResult( id=safe_guid, name=safe_filename, year=None, score=100, lang=lang ) )
        Log(u''.ljust(157, '='))
        return
      else:  Log('search() - id not found')
  
  try:
    json_video_details = json_load(YOUTUBE_VIDEO_SEARCH, String.Quote(filename, usePlus=False))
    if Dict(json_video_details, 'pageInfo', 'totalResults'):
      Log.Info(u'filename: "{}", title:        "{}"'.format(filename, Dict(json_video_details, 'items', 0, 'snippet', 'title')))
      Log.Info(u'filename: "{}", channelTitle: "{}"'.format(filename, Dict(json_video_details, 'items', 0, 'snippet', 'channelTitle')))
      if filename == Dict(json_video_details, 'items', 0, 'snippet', 'channelTitle'):
        Log.Info(u'filename: "{}", found exact matching YouTube title: "{}", description: "{}"'.format(filename, Dict(json_video_details, 'items', 0, 'snippet', 'channelTitle'), Dict(json_video_details, 'items', 0, 'snippet', 'description')))
        safe_guid = create_youtube_guid('channel', Dict(json_video_details, 'items', 0, 'id', 'channelId'), dir)
        safe_filename = xml_safe(filename)
        results.Append( MetadataSearchResult( id=safe_guid, name=safe_filename, year=None, score=100, lang=lang ) )
        Log(u''.ljust(157, '='))
        return
      else:  Log.Info(u'search() - no id in title nor matching YouTube title: "{}", closest match: "{}", description: "{}"'.format(filename, Dict(json_video_details, 'items', 0, 'snippet', 'channelTitle'), Dict(json_video_details, 'items', 0, 'snippet', 'description')))
    elif 'error' in json_video_details:  Log.Info(u'search() - code: "{}", message: "{}"'.format(Dict(json_video_details, 'error', 'code'), Dict(json_video_details, 'error', 'message')))
  except Exception as e:  
    Log(u'search() - Could not retrieve data from YouTube for: "{}", Exception: "{}"'.format(filename, e))
    track_error('search_api_failed', str(e))

  library, root, path = GetLibraryRootPath(dir)
  # VERBESSERT: Extrahiere sauberen Seriennamen aus Ordnerpfad
  series_name = os.path.basename(dir)  # Verwende Ordnername statt Dateiname
  series_name = re.sub(r'\[(UC|PL|UU|FL|LP|RD|HC)[a-zA-Z0-9\-_]{16,32}\]', '', series_name).strip()  # Entferne alle YouTube-IDs
  series_name = re.sub(r'\s+', ' ', series_name).strip()     # Bereinige Leerzeichen

  Log(u'Putting folder name "{}" as guid since no assign channel id or playlist id was assigned'.format(series_name))
  # XML-SAFE: Säubere alle Werte - KRITISCH für GUID!
  safe_series_name = xml_safe(series_name if series_name else displayname)
  safe_displayname = xml_safe(displayname)
  safe_path_part = xml_safe(path.split(os.sep)[-2] if os.sep in path else '')
  safe_guid = create_youtube_guid('folder', safe_path_part, dir)
  results.Append( MetadataSearchResult( 
    id=safe_guid, 
    name=safe_series_name,  # Verwende bereinigten Ordnernamen
    year=None, score=70, lang=lang 
  ))
  Log(''.ljust(157, '='))

### Download metadata using unique ID ###
def Update(metadata, media, lang, force, movie):
  Log(u'=== update(lang={}, force={}, movie={}) ==='.format(lang, force, movie))
  
  # KRITISCHER FIX: Sichere GUID-Parsing mit neuer Struktur
  try:
    guid_parts = metadata.id.split('://')[-1].split('|')
    if len(guid_parts) >= 3:
      temp1, guid_with_type, series_folder = guid_parts[0], guid_parts[1], "|".join(guid_parts[2:])
      
      # Erkenne GUID-Typ und extrahiere ID
      if guid_with_type.startswith('ch:'):
        guid_type = 'channel'
        guid = guid_with_type[3:]  # Entferne 'ch:' Präfix
      elif guid_with_type.startswith('pl:'):
        guid_type = 'playlist'
        guid = guid_with_type[3:]  # Entferne 'pl:' Präfix
      elif guid_with_type.startswith('v:'):
        guid_type = 'video'
        guid = guid_with_type[2:]  # Entferne 'v:' Präfix
      else:
        guid_type = 'unknown'
        guid = guid_with_type
        
      Log.Info('Parsed GUID - Type: {}, ID: {}, Folder: {}'.format(guid_type, guid, series_folder))
    else:
      temp1, guid, series_folder = "youtube", "unknown", "unknown"
      guid_type = 'unknown'
    
    # Alle Teile bereinigen
    guid = xml_safe(guid)
    series_folder = xml_safe(series_folder)
    
  except Exception as e:
    Log.Error('GUID parsing error: {}'.format(str(e)))
    guid, series_folder, guid_type = "unknown", "unknown", 'unknown'
  
  dir                        = sanitize_path(GetMediaDir(media, movie))
  channel_id                 = guid if guid.startswith('UC') or guid.startswith('HC') or guid_type == 'channel' else ''
  channel_title              = ""
  json_playlist_details      = {}
  json_playlist_items        = {}
  json_channel_items         = {}
  json_channel_details       = {}
  json_video_details         = {}
  series_folder              = sanitize_path(series_folder)
  episodes                   = 0  # Für Cache-Cleanup

  # PERFORMANCE: Erkenne Initial Scan vs Update-Modus
  is_initial_scan = True
  if not movie:  # Nur für TV-Shows/Series relevant
    try:
      # Prüfe ob bereits Metadaten vorhanden sind
      has_existing_metadata = len(metadata.seasons) > 0
      if has_existing_metadata:
        is_initial_scan = False
        Log.Info(u'[UPDATE MODE] Incremental update detected - using optimized caching')
      else:
        Log.Info(u'[INITIAL SCAN] First scan detected - loading all metadata')
    except:
      is_initial_scan = True  # Fallback zu Initial Scan bei Fehlern

  # Setze Standard-Titel basierend auf Ordnername
  if not (len(guid)>2 and guid[0:2] in ('PL', 'UU', 'FL', 'LP', 'RD')) and guid_type != 'playlist':  
    folder_name = os.path.basename(dir)
    clean_title = re.sub(r'\[(UC|PL|UU|FL|LP|RD|HC)[a-zA-Z0-9\-_]{16,32}\]', '', folder_name).strip()
    clean_title = re.sub(r'\s+', ' ', clean_title).strip()
    metadata.title = xml_safe(clean_title if clean_title else folder_name)  # XML-SAFE
  Log(u''.ljust(157, '='))
    
  ### Movie Library ###
  if movie:

    ### Movie - JSON call ###############################################################################################################
    filename = media.items[0].parts[0].file if movie else media.filename or media.show
    dir = GetMediaDir(media, movie)
    try:                    filename = sanitize_path(filename)
    except Exception as e:  Log('update() - Exception1: filename: "{}", e: "{}"'.format(filename, e))
    try:                    filename = os.path.basename(filename)
    except Exception as e:  Log('update() - Exception2: filename: "{}", e: "{}"'.format(filename, e))
    try:                    filename = urllib2.unquote(filename)
    except Exception as e:  Log('update() - Exception3: filename: "{}", e: "{}"'.format(filename, e))

    json_filename = os.path.join(dir, os.path.splitext(filename)[0]+ ".info.json")
    Log(u'Update: Searching for info file: {}, dir:{}'.format(json_filename, GetMediaDir(media, movie, True)))
    if os.path.exists(json_filename):
      try:             json_video_details = load_json_file_safe(json_filename)  # Verbesserte Funktion verwenden
      except IOError:  guid = None
      else:    
        if json_video_details:  # Zusätzliche Prüfung
          guid          = Dict(json_video_details, 'id')
          channel_id    = Dict(json_video_details, 'channel_id')

          ### Movie - Local JSON
          Log.Info(u'update() using json file json_video_details - Loaded video details from: "{}"'.format(json_filename))
          metadata.title                   = xml_safe(Dict(json_video_details, 'title'));                                  Log(u'series title:       "{}"'.format(Dict(json_video_details, 'title')))  # XML-SAFE
          metadata.summary                 = xml_safe(Dict(json_video_details, 'description'));                            Log(u'series description: '+Dict(json_video_details, 'description').replace('\n', '. '))  # XML-SAFE

          if Prefs['use_crowd_sourced_titles'] == True:
            crowd_sourced_title = DeArrow(guid)
            if crowd_sourced_title != '':
              metadata.original_title = metadata.title
              metadata.summary = xml_safe('Original Title: ' + metadata.title + '\r\n\r\n' + metadata.summary)  # XML-SAFE
              metadata.title = xml_safe(crowd_sourced_title)  # XML-SAFE

          metadata.duration = Dict(json_video_details, 'duration'); Log(u'series duration: "{}"->"{}"'.format(Dict(json_video_details, 'duration'), metadata.duration))
          metadata.genres = Dict(json_video_details, 'categories'); Log(u'genres: '+str([x for x in metadata.genres]))
          
          # SICHERES DATUM-PARSING FÜR MOVIES - JSON
          upload_date = Dict(json_video_details, 'upload_date')
          if upload_date:
            try:
              date = Datetime.ParseDate(upload_date)
              if date:
                metadata.originally_available_at = date.date()
                metadata.year = date.year
                Log(u'date: "{}"'.format(upload_date))
              else:
                Log.Info(u'Could not parse movie date: "{}"'.format(upload_date))
            except Exception as e:
              Log.Info(u'Movie date parsing error: "{}", error: {}'.format(upload_date, str(e)))
          else:
            Log.Info(u'No upload_date found in movie JSON')
          
          thumb = get_thumb(json_video_details)
          if thumb and thumb not in metadata.posters:
            Log(u'poster: "{}" added'.format(thumb))
            metadata.posters[thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
          else:  Log(u'thumb: "{}" already present'.format(thumb))
          if Dict(json_video_details, 'statistics', 'likeCount') and int(Dict(json_video_details, 'like_count')) > 0 and Dict(json_video_details, 'dislike_count') and int(Dict(json_video_details, 'dislike_count')) > 0:
            metadata.rating = float(10*int(Dict(json_video_details, 'like_count'))/(int(Dict(json_video_details, 'dislike_count'))+int(Dict(json_video_details, 'like_count'))));  Log(u'rating: {}'.format(metadata.rating))
          if Prefs['add_user_as_director']:
            metadata.directors.clear()
            try:
              director = xml_safe(Dict(json_video_details, 'uploader'));  # XML-SAFE
              meta_director = metadata.directors.new()
              meta_director.name = director
              Log('director: '+ director)
            except:  pass
          return

    ### Movie - API call ################################################################################################################
    Log(u'update() using api - guid: {}, dir: {}, metadata.id: {}'.format(guid, dir, metadata.id))
    try:     json_video_details = json_load(YOUTUBE_json_video_details, guid)['items'][0]
    except:  
      Log(u'json_video_details - Could not retrieve data from YouTube for: ' + guid)
      track_error('movie_api_failed', guid)
    else:
      Log('Movie mode - json_video_details - Loaded video details from: "{}"'.format(YOUTUBE_json_video_details.format(guid, 'personal_key')))
      
      # SICHERES DATUM-PARSING FÜR MOVIES - API
      published_at = json_video_details['snippet']['publishedAt']
      if published_at:
        try:
          date = Datetime.ParseDate(published_at)
          if date:
            metadata.originally_available_at = date.date()
            metadata.year = date.year
            Log('date: "{}"'.format(published_at))
          else:
            Log.Info('Could not parse API movie date: "{}"'.format(published_at))
        except Exception as e:
          Log.Info('API movie date parsing error: "{}", error: {}'.format(published_at, str(e)))
      else:
        Log.Info('No publishedAt found in API response')
      
      metadata.title = xml_safe(json_video_details['snippet']['title']); Log(u'series title: "{}"'.format(json_video_details['snippet']['title']))  # XML-SAFE
      metadata.summary = xml_safe(json_video_details['snippet']['description']); Log(u'series description: '+json_video_details['snippet']['description'].replace('\n', '. '))  # XML-SAFE

      if Prefs['use_crowd_sourced_titles'] == True:
        crowd_sourced_title = DeArrow(guid)
        if crowd_sourced_title != '':
          metadata.original_title = metadata.title
          metadata.summary = xml_safe('Original Title: ' + metadata.title + '\r\n\r\n' + metadata.summary)  # XML-SAFE
          metadata.title = xml_safe(crowd_sourced_title)  # XML-SAFE

      metadata.duration = ISO8601DurationToSeconds(json_video_details['contentDetails']['duration'])*1000; Log(u'series duration: "{}"->"{}"'.format(json_video_details['contentDetails']['duration'], metadata.duration))
      metadata.genres = [YOUTUBE_CATEGORY_ID[id] for id in json_video_details['snippet']['categoryId'].split(',')]; Log(u'genres: '+str([x for x in metadata.genres]))
      thumb = json_video_details['snippet']['thumbnails']['default']['url']; Log(u'thumb: "{}"'.format(thumb))
      if thumb and thumb not in metadata.posters:
        Log(u'poster: "{}"'.format(thumb))
        metadata.posters[thumb] = Proxy.Media(HTTP.Request(Dict(json_video_details, 'snippet', 'thumbnails', 'maxres', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'medium', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'standard', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'high', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'default', 'url')).content, sort_order=1)
      if Dict(json_video_details, 'statistics', 'likeCount') and int(json_video_details['statistics']['likeCount']) > 0 and Dict(json_video_details, 'statistics', 'dislikeCount') and int(Dict(json_video_details, 'statistics', 'dislikeCount')) > 0:
        metadata.rating = float(10*int(json_video_details['statistics']['likeCount'])/(int(json_video_details['statistics']['dislikeCount'])+int(json_video_details['statistics']['likeCount']))); Log('rating: {}'.format(metadata.rating))
      if Prefs['add_user_as_director']:
        metadata.directors.clear()
        try:
          meta_director = metadata.directors.new()
          meta_director.name = xml_safe(json_video_details['snippet']['channelTitle'])  # XML-SAFE
          Log(u'director: '+json_video_details['snippet']['channelTitle'])
        except Exception as e:  Log.Info(u'[!] add_user_as_director exception: {}'.format(e))
      return
  
  ### TV series Library ###
  else:
    title=""
    ### Collection tag for grouping folders ###
    library, root, path = GetLibraryRootPath(dir)
    series_root_folder=''
    Log.Info(u'[ ] library:    "{}"'.format(library))
    Log.Info(u'[ ] root:       "{}"'.format(root   ))
    Log.Info(u'[ ] path:       "{}"'.format(path   ))
    Log.Info(u'[ ] dir:        "{}"'.format(dir    ))
    metadata.studio = 'YouTube'
    if not path in ('_unknown_folder', '.'):
      #Log.Info('[ ] series root folder:        "{}"'.format(os.path.join(root, path.split(os.sep, 1)[0])))
      series_root_folder  = os.path.join(root, path.split(os.sep, 1)[0] if os.sep in path else path) 
      Log.Info(u'[ ] series_root_folder: "{}"'.format(series_root_folder))
      list_files      = os.listdir(series_root_folder) if os.path.exists(series_root_folder) else []
      subfolder_count = len([file for file in list_files if os.path.isdir(os.path.join(series_root_folder, file))])
      Log.Info(u'[ ] subfolder_count:    "{}"'.format(subfolder_count   ))

      ### Extract season and transparent folder to reduce complexity and use folder as serie name ###
      reverse_path, season_folder_first = list(reversed(path.split(os.sep))), False
      SEASON_RX = [ '^Specials',                                                                                                                                           # Specials (season 0)
                    '^(?P<show>.*)?[\._\-\–" ]*?(Season|Series|Book|Saison|Livre|Temporada|[Ss])[\._\–"\- ]*?(?P<season>\d{1,4}).*?',                                        # (title) S01
                    '^(?P<show>.*)?[\._\-\–" ]*?Volume[\._\-\–" ]*?(?P<season>(?=[MDCLXVI])M*D?C{0,4}L?X{0,4}V?I{0,4}).*?',                                                  # (title) S01
                    '^(Saga|(Story )?Ar[kc])']                                                                                                                             # Last entry, folder name droped but files kept: Saga / Story Ar[kc] / Ar[kc]
      for folder in reverse_path[:-1]:                 # remove root folder from test, [:-1] Doesn't thow errors but gives an empty list if items don't exist, might not be what you want in other cases
        for rx in SEASON_RX[:-1]:                      # in anime, more specials folders than season folders, so doing it first
          if re.match(rx, folder, re.IGNORECASE):      # get season number but Skip last entry in seasons (skipped folders)
            reverse_path.remove(folder)                # Since iterating slice [:] or [:-1] doesn't hinder iteration. All ways to remove: reverse_path.pop(-1), reverse_path.remove(thing|array[0])
            if rx!=SEASON_RX[-1] and len(reverse_path)>=2 and folder==reverse_path[-2]:  season_folder_first = True
            break

      if len(reverse_path)>1 and not season_folder_first and subfolder_count>1:  ### grouping folders only ###
        Log.Info("Grouping folder found, root: {}, path: {}, Grouping folder: {}, subdirs: {}, reverse_path: {}".format(root, path, os.path.basename(series_root_folder), subfolder_count, reverse_path))
        collection = xml_safe(re.sub(r'\[.*\]', '', reverse_path[-1]).strip())  # XML-SAFE
        Log.Info('[ ] collections:        "{}"'.format(collection))
        if collection not in metadata.collections:  metadata.collections=[collection]
      else:  Log.Info("Grouping folder not found or single folder, root: {}, path: {}, Grouping folder: {}, subdirs: {}, reverse_path: {}".format(root, path, os.path.basename(series_root_folder), subfolder_count, reverse_path))

    ### Series - Playlist ###############################################################################################################
    if (len(guid)>2 and guid[0:2] in ('PL', 'UU', 'FL', 'LP', 'RD')) or guid_type == 'playlist':
      Log.Info('[?] json_playlist_details for GUID: {}'.format(guid))
      try:                    json_playlist_details = json_load_cached(YOUTUBE_PLAYLIST_DETAILS, guid, force_refresh=is_initial_scan)['items'][0]
      except Exception as e:  
        Log('[!] json_playlist_details exception: {}, url: {}'.format(e, YOUTUBE_PLAYLIST_DETAILS.format(guid, 'personal_key')))
        track_error('playlist_details_failed', str(e))
        # FALLBACK für Playlists: Verwende Ordnername wenn API fehlschlägt
        if not metadata.title:
          folder_name = os.path.basename(dir)
          clean_title = re.sub(r'\[(UC|PL|UU|FL|LP|RD|HC)[a-zA-Z0-9\-_]{16,32}\]', '', folder_name).strip()
          metadata.title = xml_safe(clean_title if clean_title else folder_name)  # XML-SAFE
          Log.Info('[!] API-Fallback: Playlist-Titel aus Ordnername gesetzt: "{}"'.format(metadata.title))
      else:
        Log.Info('[?] json_playlist_details: {}'.format(json_playlist_details.keys()))
        channel_id                       = Dict(json_playlist_details, 'snippet', 'channelId');                               Log.Info('[ ] channel_id: "{}"'.format(channel_id))
        title                            = xml_safe(sanitize_path(Dict(json_playlist_details, 'snippet', 'title')));                    Log.Info('[ ] title:      "{}"'.format(title))  # XML-SAFE
        if title: metadata.title = title
        
        # SICHERES DATUM-PARSING FÜR PLAYLISTS
        published_at = Dict(json_playlist_details, 'snippet', 'publishedAt')
        if published_at:
          try:
            parsed_date = Datetime.ParseDate(published_at)
            if parsed_date:
              metadata.originally_available_at = parsed_date.date()
              Log.Info('[ ] publishedAt: {}'.format(published_at))
            else:
              Log.Info('[ ] Could not parse playlist date: "{}"'.format(published_at))
          except Exception as e:
            Log.Info('[ ] Playlist date parsing error: "{}", error: {}'.format(published_at, str(e)))
        
        metadata.summary = xml_safe(Dict(json_playlist_details, 'snippet', 'description')); Log.Info('[ ] summary: "{}"'.format((Dict(json_playlist_details, 'snippet', 'description').replace('\n', '. '))))  # XML-SAFE

        if Prefs['use_crowd_sourced_titles'] == True:
          crowd_sourced_title = DeArrow(guid)
          if crowd_sourced_title != '':
            metadata.summary = xml_safe('Original Title: ' + metadata.title + '\r\n\r\n' + metadata.summary)  # XML-SAFE
            metadata.title = xml_safe(crowd_sourced_title)  # XML-SAFE

      Log.Info('[?] json_playlist_items')
      try:                    json_playlist_items = json_load_cached(YOUTUBE_PLAYLIST_ITEMS, guid, force_refresh=is_initial_scan)
      except Exception as e:  
        Log.Info('[!] json_playlist_items exception: {}, url: {}'.format(e, YOUTUBE_PLAYLIST_ITEMS.format(guid, 'personal_key')))
        track_error('playlist_items_failed', str(e))
      else:
        Log.Info('[?] json_playlist_items: {}'.format(json_playlist_items.keys()))
        first_video = sorted(Dict(json_playlist_items, 'items'), key=lambda i: Dict(i, 'contentDetails', 'videoPublishedAt'))[0]
        thumb = Dict(first_video, 'snippet', 'thumbnails', 'maxres', 'url') or Dict(first_video, 'snippet', 'thumbnails', 'medium', 'url') or Dict(first_video, 'snippet', 'thumbnails', 'standard', 'url') or Dict(first_video, 'snippet', 'thumbnails', 'high', 'url') or Dict(first_video, 'snippet', 'thumbnails', 'default', 'url')
        if thumb and thumb not in metadata.posters:  Log('[ ] posters:   {}'.format(thumb));  metadata.posters [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1 if Prefs['media_poster_source']=='Episode' else 2)
        else:                                        Log('[X] posters:   {}'.format(thumb))
        if thumb and thumb not in metadata.art:      Log('[X] art:       {}'.format(thumb));  metadata.art [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
        else:                                        Log('[ ] art:       {}'.format(thumb))
        if thumb and thumb not in metadata.banners:  Log('[X] banners:   {}'.format(thumb));  metadata.banners [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
        else:                                        Log('[ ] banners:   {}'.format(thumb))
    
    ### Series - Channel ###############################################################################################################
    if (channel_id.startswith('UC') or channel_id.startswith('HC')) or guid_type == 'channel':
      # Verwende channel_id wenn vorhanden, sonst guid
      actual_channel_id = channel_id if channel_id else guid
      Log.Info('[?] Processing Channel ID: {}'.format(actual_channel_id))
      
      try:
        # PERFORMANCE: Nutze Cache für Channel-Details/Items (außer bei force_refresh)
        json_channel_details  = json_load_cached(YOUTUBE_CHANNEL_DETAILS, actual_channel_id, force_refresh=is_initial_scan)['items'][0]
        json_channel_items    = json_load_cached(YOUTUBE_CHANNEL_ITEMS, actual_channel_id, force_refresh=is_initial_scan)
      except Exception as e:  
        Log('exception: {}, url: {}'.format(e, actual_channel_id))
        track_error('channel_api_failed', str(e))
      else:
        
        if not title:
          title          = xml_safe(re.sub( "\s*\[.*?\]\s*"," ",series_folder))  #instead of path use series foldername  # XML-SAFE
          metadata.title = title
        Log.Info('[ ] title:        "{}", metadata.title: "{}"'.format(title, metadata.title))
        if not Dict(json_playlist_details, 'snippet', 'description'):
          if Dict(json_channel_details, 'snippet', 'description'):  metadata.summary = xml_safe(sanitize_path(Dict(json_channel_details, 'snippet', 'description')))  # XML-SAFE
          else:
            summary  = u'Channel with {} videos, '.format(Dict(json_channel_details, 'statistics', 'videoCount'))
            summary += u'{} subscribers, '.format(Dict(json_channel_details, 'statistics', 'subscriberCount'))
            summary += u'{} views'.format(Dict(json_channel_details, 'statistics', 'viewCount'))
            metadata.summary = xml_safe(sanitize_path(summary));  Log.Info(u'[ ] summary:     "{}"'.format(summary))  #  # XML-SAFE

        if Prefs['use_crowd_sourced_titles'] == True:
          crowd_sourced_title = DeArrow(guid)
          if crowd_sourced_title != '':
            metadata.summary = xml_safe('Original Title: ' + metadata.title + '\r\n\r\n' + metadata.summary)  # XML-SAFE
            metadata.title = xml_safe(crowd_sourced_title)  # XML-SAFE

        if Dict(json_channel_details,'snippet','country') and Dict(json_channel_details,'snippet','country') not in metadata.countries:
          metadata.countries.add(Dict(json_channel_details,'snippet','country'));  Log.Info('[ ] country: {}'.format(Dict(json_channel_details,'snippet','country') ))

        ### Playlist with cast coming from multiple chan entries in youtube.id file ###############################################################################################################
        if os.path.exists(os.path.join(dir, 'youtube.id')):
          with open(os.path.join(dir, 'youtube.id')) as f:
            metadata.roles.clear()
            for line in f.readlines():
              try:                    json_channel_details = json_load(YOUTUBE_CHANNEL_DETAILS, line.rstrip())['items'][0]
              except Exception as e:  
                Log('exception: {}, url: {}'.format(e, guid))
                track_error('youtube_id_file_failed', str(e))
              else:
                Log.Info('[?] json_channel_details: {}'.format(json_channel_details.keys()))
                Log.Info('[ ] title:       "{}"'.format(Dict(json_channel_details, 'snippet', 'title'      )))
                if not Dict(json_playlist_details, 'snippet', 'description'):
                  if Dict(json_channel_details, 'snippet', 'description'):  metadata.summary = xml_safe(sanitize_path(Dict(json_channel_details, 'snippet', 'description')))  # XML-SAFE
                  #elif guid.startswith('PL'):  metadata.summary = 'No Playlist nor Channel summary'
                  else:
                    summary  = u'Channel with {} videos, '.format(Dict(json_channel_details, 'statistics', 'videoCount'     ))
                    summary += u'{} subscribers, '.format(Dict(json_channel_details, 'statistics', 'subscriberCount'))
                    summary += u'{} views'.format(Dict(json_channel_details, 'statistics', 'viewCount'      ))
                    metadata.summary = xml_safe(sanitize_path(summary)) #or 'No Channel summary'  # XML-SAFE
                    Log.Info(u'[ ] summary:     "{}"'.format(Dict(json_channel_details, 'snippet', 'description').replace('\n', '. ')))  #
                
                if Dict(json_channel_details,'snippet','country') and Dict(json_channel_details,'snippet','country') not in metadata.countries:
                  metadata.countries.add(Dict(json_channel_details,'snippet','country'));  Log.Info('[ ] country: {}'.format(Dict(json_channel_details,'snippet','country') ))
                
                thumb_channel = Dict(json_channel_details, 'snippet', 'thumbnails', 'medium', 'url') or Dict(json_channel_details, 'snippet', 'thumbnails', 'high', 'url')   or Dict(json_channel_details, 'snippet', 'thumbnails', 'default', 'url')
                role       = metadata.roles.new()
                role.role  = xml_safe(sanitize_path(Dict(json_channel_details, 'snippet', 'title')))  # XML-SAFE
                role.name  = xml_safe(sanitize_path(Dict(json_channel_details, 'snippet', 'title')))  # XML-SAFE
                role.photo = thumb_channel
                Log.Info('[ ] role:        {}'.format(Dict(json_channel_details,'snippet','title')))
                
                thumb = Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvLowImageUrl' ) or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvMediumImageUrl') \
                  or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvHighImageUrl') or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvImageUrl'      )
                external_banner_url = Dict(json_channel_details, 'brandingSettings', 'image', 'bannerExternalUrl')
                if not thumb and external_banner_url: thumb = '{}=s1920'.format(external_banner_url)
                if thumb and thumb not in metadata.art:      Log('[X] art:       {}'.format(thumb));  metadata.art [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
                else:                                        Log('[ ] art:       {}'.format(thumb))
                if thumb and thumb not in metadata.banners:  Log('[X] banners:   {}'.format(thumb));  metadata.banners [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
                else:                                        Log('[ ] banners:   {}'.format(thumb))
                if thumb_channel and thumb_channel not in metadata.posters:
                  Log('[X] posters:   {}'.format(thumb_channel))
                  metadata.posters [thumb_channel] = Proxy.Media(HTTP.Request(thumb_channel).content, sort_order=1 if Prefs['media_poster_source']=='Channel' else 2)
                  #metadata.posters.validate_keys([thumb_channel])
                else:                                                        Log('[ ] posters:   {}'.format(thumb_channel))
        
        ### Cast comes from channel
        else:    
          thumb         = Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvLowImageUrl' ) or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvMediumImageUrl') \
                       or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvHighImageUrl') or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvImageUrl'      )
          external_banner_url = Dict(json_channel_details, 'brandingSettings', 'image', 'bannerExternalUrl')
          if not thumb and external_banner_url: thumb = '{}=s1920'.format(external_banner_url)
          if thumb and thumb not in metadata.art:      Log(u'[X] art:       {}'.format(thumb));  metadata.art [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
          else:                                        Log(u'[ ] art:       {}'.format(thumb))
          if thumb and thumb not in metadata.banners:  Log(u'[X] banners:   {}'.format(thumb));  metadata.banners [thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
          else:                                        Log(u'[ ] banners:   {}'.format(thumb))
          thumb_channel = Dict(json_channel_details, 'snippet', 'thumbnails', 'medium', 'url') or Dict(json_channel_details, 'snippet', 'thumbnails', 'high', 'url')   or Dict(json_channel_details, 'snippet', 'thumbnails', 'default', 'url')
          if thumb_channel and thumb_channel not in metadata.posters:
            #thumb_channel = sanitize_path(thumb_channel)
            Log(u'[X] posters:   {}'.format(thumb_channel))
            metadata.posters [thumb_channel] = Proxy.Media(HTTP.Request(thumb_channel).content, sort_order=1 if Prefs['media_poster_source']=='Channel' else 2)
            #metadata.posters.validate_keys([thumb_channel])
          else:                                        Log('[ ] posters:   {}'.format(thumb_channel))
          metadata.roles.clear()
          role       = metadata.roles.new()
          role.role  = xml_safe(sanitize_path(Dict(json_channel_details, 'snippet', 'title')))  # XML-SAFE
          role.name  = xml_safe(sanitize_path(Dict(json_channel_details, 'snippet', 'title')))  # XML-SAFE
          role.photo = thumb_channel
          Log.Info(u'[ ] role:        {}'.format(Dict(json_channel_details,'snippet','title')))
          #if not Dict(json_playlist_details, 'snippet', 'publishedAt'):  metadata.originally_available_at = Datetime.ParseDate(Dict(json_channel_items, 'snippet', 'publishedAt')).date();  Log.Info('[ ] publishedAt:  {}'.format(Dict(json_channel_items, 'snippet', 'publishedAt' )))
           
    

# NOT PLAYLIST NOR CHANNEL GUID - KORRIGIERT: Channel-Info aus Ordnername extrahieren
    if guid_type not in ('playlist', 'channel') and not (channel_id.startswith('UC') or channel_id.startswith('HC')):  
      Log.Info('No valid GUID type - extrahiere Channel-ID aus Ordnername')
      
      # KORREKTUR: Channel-ID aus Ordnername extrahieren - verwende 'dir'
      folder_name = os.path.basename(dir)
      Log.Info('Analysiere Ordnername fuer Channel-ID: "{}"'.format(folder_name))
      
      # KORREKTUR: Entferne alle YouTube-IDs aus Seriennamen
      clean_title = re.sub(r'\[(UC|PL|UU|FL|LP|RD|HC)[a-zA-Z0-9_-]{16,32}\]', '', folder_name).strip()
      metadata.title = xml_safe(clean_title)  # XML-SAFE
      Log.Info('Bereinigte Serie-Titel gesetzt: "{}"'.format(clean_title))
      
      # Regex um Channel-ID aus Ordnername zu extrahieren: [UCxxxxxxxx]
      channel_match = re.search(r'\[([UC][a-zA-Z0-9_-]{22,23})\]', folder_name)
      
      if channel_match:
        extracted_channel_id = channel_match.group(1)
        Log.Info('Channel-ID aus Ordnername extrahiert: "{}"'.format(extracted_channel_id))
        
        # JETZT API-AUFRUF für Channel-Details (Name, Avatar, etc.)
        try:
          Log.Info('Starte API-Aufruf fuer Channel-Details: {}'.format(extracted_channel_id))
          json_channel_details = json_load(YOUTUBE_CHANNEL_DETAILS, extracted_channel_id)['items'][0]
          Log.Info('Channel-API erfolgreich - Titel: "{}"'.format(Dict(json_channel_details, 'snippet', 'title')))
          
          # Channel-Informationen setzen
          api_channel_title = xml_safe(Dict(json_channel_details, 'snippet', 'title'))  # XML-SAFE
          if api_channel_title:
            # Channel als Role/Cast setzen
            metadata.roles.clear()
            role = metadata.roles.new()
            role.role = api_channel_title
            role.name = api_channel_title
            
            # Channel-Avatar von API
            thumb_channel = Dict(json_channel_details, 'snippet', 'thumbnails', 'medium', 'url') or Dict(json_channel_details, 'snippet', 'thumbnails', 'high', 'url') or Dict(json_channel_details, 'snippet', 'thumbnails', 'default', 'url')
            if thumb_channel:
              role.photo = thumb_channel
              Log.Info('Channel-Role mit API-Avatar gesetzt: "{}"'.format(api_channel_title))
              
              # Setze Channel-Avatar als Serie-Poster
              if thumb_channel not in metadata.posters:
                Log.Info('Channel-Poster von API gesetzt: {}'.format(thumb_channel))
                metadata.posters[thumb_channel] = Proxy.Media(HTTP.Request(thumb_channel).content, sort_order=1 if Prefs['media_poster_source']=='Channel' else 2)
              
              # Setze Channel-Banner als Art/Fanart
              thumb_banner = Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvLowImageUrl') or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvMediumImageUrl') or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvHighImageUrl') or Dict(json_channel_details, 'brandingSettings', 'image', 'bannerTvImageUrl')
              external_banner_url = Dict(json_channel_details, 'brandingSettings', 'image', 'bannerExternalUrl')  
              if not thumb_banner and external_banner_url: 
                thumb_banner = '{}=s1920'.format(external_banner_url)
              
              if thumb_banner and thumb_banner not in metadata.art:
                Log.Info('Channel-Banner als Art gesetzt: {}'.format(thumb_banner))
                metadata.art[thumb_banner] = Proxy.Media(HTTP.Request(thumb_banner).content, sort_order=1)
              if thumb_banner and thumb_banner not in metadata.banners:
                Log.Info('Channel-Banner als Fanart gesetzt: {}'.format(thumb_banner))
                metadata.banners[thumb_banner] = Proxy.Media(HTTP.Request(thumb_banner).content, sort_order=1)
          
          # Setze Channel-Beschreibung als Serie-Beschreibung
          api_channel_description = xml_safe(Dict(json_channel_details, 'snippet', 'description'))  # XML-SAFE
          if api_channel_description:
            metadata.summary = api_channel_description
            Log.Info('Serie-Beschreibung von Channel-API gesetzt')
          else:
            # Fallback: Statistiken als Beschreibung
            summary = u'Channel with {} videos, '.format(Dict(json_channel_details, 'statistics', 'videoCount'))
            summary += u'{} subscribers, '.format(Dict(json_channel_details, 'statistics', 'subscriberCount'))
            summary += u'{} views'.format(Dict(json_channel_details, 'statistics', 'viewCount'))
            metadata.summary = xml_safe(summary)  # XML-SAFE
            Log.Info('Serie-Beschreibung mit Channel-Statistiken gesetzt')
          
          # Setze Land falls verfügbar
          if Dict(json_channel_details, 'snippet', 'country') and Dict(json_channel_details, 'snippet', 'country') not in metadata.countries:
            metadata.countries.add(Dict(json_channel_details, 'snippet', 'country'))
            Log.Info('Country gesetzt: {}'.format(Dict(json_channel_details, 'snippet', 'country')))
        
        except Exception as e:
          Log.Warn('Channel-API Fehler für {}: {}'.format(extracted_channel_id, str(e)))
          track_error('extracted_channel_api_failed', str(e))
          # Fallback: Verwende Channel-Name aus Ordnername
          channel_name_from_folder = folder_name.split('[')[0].strip()
          if channel_name_from_folder:
            metadata.roles.clear()
            role = metadata.roles.new()
            role.role = xml_safe(channel_name_from_folder)  # XML-SAFE
            role.name = xml_safe(channel_name_from_folder)  # XML-SAFE
            Log.Info('Fallback: Channel-Role aus Ordnername gesetzt: "{}"'.format(channel_name_from_folder))
      
      else:
        Log.Info('Keine Channel-ID im Ordnernamen gefunden: "{}"'.format(folder_name))
        # Fallback: Verwende nur Ordnername
        metadata.roles.clear()
        role = metadata.roles.new()  
        role.role = xml_safe(folder_name)  # XML-SAFE
        role.name = xml_safe(folder_name)  # XML-SAFE
        Log.Info('Fallback: Role aus Ordnername gesetzt: "{}"'.format(folder_name))
 
    ### Season + Episode loop ###
    genre_array = {}

    # WICHTIG: Extrahiere Channel-Titel aus erster JSON-Datei für Serientitel
    # ABER NUR für Channels ohne sauberen Titel, NICHT für Playlists!
    Log.Info(u'[ ] DEBUG: metadata.title vor Prüfung: "{}"'.format(metadata.title))
    Log.Info(u'[ ] DEBUG: guid_type: "{}", ist Playlist: {}'.format(guid_type, guid_type == 'playlist'))
    
    if guid_type != 'playlist' and (not metadata.title or os.sep in metadata.title or re.search(r'\[(UC|PL|UU|FL|LP|RD|HC)[a-zA-Z0-9\-_]{16,32}\]', metadata.title)):
        Log.Info(u'[ ] DEBUG: Bedingung erfüllt - starte JSON-Extraktion')
        first_json_channel_title = ""
        list_files = os.listdir(series_root_folder) if os.path.exists(series_root_folder) else []
        for file in sorted(list_files):
            if file.endswith(".info.json"):
                try:
                    json_content = load_json_file_safe(os.path.join(series_root_folder, file))  # Verbesserte Funktion verwenden
                    if json_content:
                        first_json_channel_title = xml_safe(Dict(json_content, 'uploader') or Dict(json_content, 'channel'))  # XML-SAFE
                        if first_json_channel_title:
                            Log.Info(u'[ ] Channel-Titel aus JSON extrahiert: "{}" (aus: {})'.format(first_json_channel_title, file))
                            break
                except:
                    continue
        
        if first_json_channel_title:
            metadata.title = first_json_channel_title
            Log.Info(u'[ ] Serientitel aus erster JSON gesetzt: "{}"'.format(metadata.title))
        else:
            # Fallback: Ordnername ohne YouTube-IDs
            folder_name = os.path.basename(dir)
            clean_title = re.sub(r'\[(UC|PL|UU|FL|LP|RD|HC)[a-zA-Z0-9\-_]{16,32}\]', '', folder_name).strip()
            metadata.title = xml_safe(clean_title if clean_title else folder_name)  # XML-SAFE
            Log.Info(u'[ ] Serientitel aus Ordnername gesetzt: "{}"'.format(metadata.title))
    else:
        Log.Info(u'[ ] DEBUG: Bedingung NICHT erfüllt - überspringe JSON-Extraktion')

    # PERFORMANCE: O(1) Lookup-Dictionary für Videos (statt O(n²) verschachtelte Schleifen)
    video_lookup_by_id = {}
    for video in Dict(json_playlist_items, 'items') or Dict(json_channel_items, 'items') or []:
        videoId = Dict(video, 'id', 'videoId') or Dict(video, 'snippet', 'resourceId', 'videoId')
        if videoId:
            video_lookup_by_id[videoId] = video
    Log.Info(u'[PERFORMANCE] Created video lookup dictionary with {} entries'.format(len(video_lookup_by_id)))

    for s in sorted(media.seasons, key=natural_sort_key):
      Log.Info(u"".ljust(157, '='))
      Log.Info(u"Season: {:>2}".format(s))
    
      for e in sorted(media.seasons[s].episodes, key=natural_sort_key):
        filename  = os.path.basename(media.seasons[s].episodes[e].items[0].parts[0].file)
        episode   = metadata.seasons[s].episodes[e]
        episodes += 1
        Log.Info('metadata.seasons[{:>2}].episodes[{:>3}] "{}"'.format(s, e, filename))

        # PERFORMANCE: O(1) Lookup statt O(n) Schleife - extrahiere videoId aus Filename
        video_found = False
        for videoId in video_lookup_by_id.keys():
          if videoId in filename:
            video = video_lookup_by_id[videoId]

            title_api = xml_safe(Dict(video, 'snippet', 'title'))  # XML-SAFE
            if title_api.lower() in ('private video', 'deleted video', 'video unavailable', ''):
                Log.Info(u'Skippe Platzhalter-Titel – verwende lokale info.json')
                continue
            episode.title = title_api
            episode.summary = xml_safe(Dict(video, 'snippet', 'description').replace('\n', '. '))  # XML-SAFE

            # SICHERES DATUM-PARSING FÜR PLAYLIST/CHANNEL ITEMS
            published_at = Dict(video, 'snippet', 'publishedAt')
            if published_at:
              try:
                parsed_date = Datetime.ParseDate(published_at)
                if parsed_date:
                  episode.originally_available_at = parsed_date.date()
                  Log.Info(u'[ ] API episode date: "{}"'.format(published_at))
              except Exception as e:
                Log.Info(u'[ ] API episode date parsing error: "{}", error: {}'.format(published_at, str(e)))

            thumb = Dict(video, 'snippet', 'thumbnails', 'high', 'url') or Dict(video, 'snippet', 'thumbnails', 'default', 'url')
            if thumb and thumb not in episode.thumbs:
                episode.thumbs[thumb] = Proxy.Media(HTTP.Request(thumb).content, sort_order=1)
                episode.thumbs.validate_keys([thumb])
            Log.Info(u'[ ] channelTitle: {}'.format(Dict(video, 'snippet', 'channelTitle')))
            video_found = True
            break


        if not video_found:  # videoId not in Playlist/channel item list

          ### OPTIMIERT: Verwende neue optimierte JSON-Suche ###
          json_video_details = populate_episode_metadata_from_info_json_optimized(series_root_folder, filename)
          
          if json_video_details:
            # Verwende lokale JSON-Daten
            videoId = Dict(json_video_details, 'id')
            Log.Info('Verwende lokale info.json fuer videoId [{}]'.format(videoId))
            Log.Info('[?] link:     "https://www.youtube.com/watch?v={}"'.format(videoId))
            
            # KORRIGIERT: Channel-Name aus JSON extrahieren
            json_channel_title = xml_safe(Dict(json_video_details, 'uploader') or Dict(json_video_details, 'channel') or Dict(json_video_details, 'uploader_id'))  # XML-SAFE
            if json_channel_title and not channel_title:
              channel_title = json_channel_title
              Log.Info(u'[ ] channel aus JSON: "{}"'.format(channel_title))
            
            # FIX: Verwende extrahierten Channel-Titel nur für echte Channels (nicht für Playlists!)
            if channel_title and guid_type != 'playlist' and not metadata.title:
                metadata.title = channel_title
                Log.Info(u'[ ] Serientitel aus JSON gesetzt: "{}"'.format(channel_title))
            
            thumb, picture = img_load(series_root_folder, filename)  #Load locally
            if not thumb:
              thumb = get_thumb(json_video_details)
              if thumb not in episode.thumbs: picture = HTTP.Request(thumb).content  
            if thumb and thumb not in episode.thumbs:
              Log.Info(u'[ ] thumbs:   "{}"'.format(thumb))
              episode.thumbs[thumb] = Proxy.Media(picture, sort_order=1)
              episode.thumbs.validate_keys([thumb])
            
            # KRITISCHER FIX: Episode-Titel sicher setzen
            raw_title = Dict(json_video_details, 'title')
            if raw_title:
              safe_title = xml_safe(raw_title)
              if safe_title and safe_title.strip():
                episode.title = safe_title
                Log.Info(u'[ ] title:    "{}"'.format(safe_title))
              else:
                episode.title = xml_safe('Episode {}'.format(e))
                Log.Warn('Episode title empty after cleaning, using fallback')
            else:
              episode.title = xml_safe('Episode {}'.format(e))
              Log.Warn('No title in JSON, using fallback')
              
            episode.summary = xml_safe(Dict(json_video_details, 'description')); Log.Info(u'[ ] summary: "{}"'.format(Dict(json_video_details, 'description').replace('\n', '. ')))  # XML-SAFE
            
            # SICHERES DATUM-PARSING FÜR EPISODES - JSON
            if len(unicode(e)) > 3:
              upload_date = Dict(json_video_details, 'upload_date')
              if upload_date:
                try:
                  parsed_date = Datetime.ParseDate(upload_date)
                  if parsed_date:
                    episode.originally_available_at = parsed_date.date()
                    Log.Info(u'[ ] date: "{}"'.format(upload_date))
                  else:
                    Log.Info(u'[ ] Could not parse date: "{}"'.format(upload_date))
                except Exception as e:
                  Log.Info(u'[ ] Date parsing error: "{}", error: {}'.format(upload_date, str(e)))
              else:
                Log.Info(u'[ ] No upload_date found in JSON')
            
            episode.duration = int(Dict(json_video_details, 'duration') or 0); Log.Info(u'[ ] duration: "{}"'.format(episode.duration))
            if Dict(json_video_details, 'like_count') and int(Dict(json_video_details, 'like_count') or 0) > 0 and Dict(json_video_details, 'dislike_count') and int(Dict(json_video_details, 'dislike_count') or 0) > 0:
              episode.rating = float(10*int(Dict(json_video_details, 'like_count'))/(int(Dict(json_video_details, 'dislike_count'))+int(Dict(json_video_details, 'like_count')))); Log('[ ] rating: "{}"'.format(episode.rating))
            
            # KORRIGIERT: Channel-Title als Director verwenden
            current_channel_title = json_channel_title or channel_title
            if current_channel_title and current_channel_title not in [role_obj.name for role_obj in episode.directors]:
              meta_director = episode.directors.new()
              meta_director.name = current_channel_title
              Log.Info(u'[ ] director: "{}"'.format(current_channel_title))

            for category  in Dict(json_video_details, 'categories') or []:  genre_array[category] = genre_array[category]+1 if category in genre_array else 1
            for tag       in Dict(json_video_details, 'tags')       or []:  genre_array[tag     ] = genre_array[tag     ]+1 if tag      in genre_array else 1
            
            Log.Info(u'[ ] genres:   "{}"'.format([x for x in metadata.genres]))  #metadata.genres.clear()
            for id in [id for id in genre_array if genre_array[id]>episodes/2 and id not in metadata.genres]:  metadata.genres.add(id)
          
          else:
            # Fallback: API-Aufruf (nur wenn keine JSON-Datei gefunden)
            Log.Info(u'Keine info.json gefunden, verwende API-Fallback fuer: {}'.format(filename))
            result = YOUTUBE_VIDEO_REGEX.search(filename)
            if result:
              videoId = result.group('id')
              Log.Info(u'# videoId [{}] not in Playlist/channel item list so loading json_video_details'.format(videoId))
              try:                    json_video_details = json_load(YOUTUBE_json_video_details, videoId)['items'][0]
              except Exception as e:  
                Log('Error: "{}"'.format(e))
                track_error('video_api_fallback_failed', str(e))
              else:
                Log.Info('[?] link:     "https://www.youtube.com/watch?v={}"'.format(videoId))
                thumb = Dict(json_video_details, 'snippet', 'thumbnails', 'maxres', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'medium', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'standard', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'high', 'url') or Dict(json_video_details, 'snippet', 'thumbnails', 'default', 'url')
                
                # KRITISCHER FIX: API Episode-Titel sicher setzen
                raw_api_title = json_video_details['snippet']['title']
                if raw_api_title:
                  safe_api_title = xml_safe(raw_api_title)
                  if safe_api_title and safe_api_title.strip():
                    episode.title = safe_api_title
                    Log.Info('[ ] title:    "{}"'.format(safe_api_title))
                  else:
                    episode.title = xml_safe('Episode {}'.format(e))
                    Log.Warn('API episode title empty after cleaning, using fallback')
                else:
                  episode.title = xml_safe('Episode {}'.format(e))
                  Log.Warn('No title in API response, using fallback')
                  
                episode.summary = xml_safe(json_video_details['snippet']['description']); Log.Info('[ ] summary: "{}"'.format(json_video_details['snippet']['description'].replace('\n', '. ')))  # XML-SAFE
                
                # SICHERES DATUM-PARSING FÜR API-EPISODES
                if len(unicode(e)) > 3:
                  published_at = json_video_details['snippet']['publishedAt']
                  if published_at:
                    try:
                      date = Datetime.ParseDate(published_at)
                      if date:
                        episode.originally_available_at = date.date()
                        Log.Info('[ ] date:     "{}"'.format(published_at))
                      else:
                        Log.Info('[ ] Invalid publishedAt format: "{}"'.format(published_at))
                    except Exception as e:
                      Log.Info('[ ] Episode API date parsing error: "{}", error: {}'.format(published_at, str(e)))
                  else:
                    Log.Info('[ ] No publishedAt found in API response')
                    
                episode.duration = ISO8601DurationToSeconds(json_video_details['contentDetails']['duration'])*1000; Log.Info('[ ] duration: "{}"->"{}"'.format(json_video_details['contentDetails']['duration'], episode.duration))
                if Dict(json_video_details, 'statistics', 'likeCount') and int(json_video_details['statistics']['likeCount']) > 0 and Dict(json_video_details, 'statistics', 'dislikeCount') and int(Dict(json_video_details, 'statistics', 'dislikeCount')) > 0:
                  episode.rating = 10*float(json_video_details['statistics']['likeCount'])/(float(json_video_details['statistics']['dislikeCount'])+float(json_video_details['statistics']['likeCount'])); Log('[ ] rating: "{}"'.format(episode.rating))
                if thumb and thumb not in episode.thumbs:
                  picture = HTTP.Request(thumb).content
                  episode.thumbs[thumb] = Proxy.Media(picture, sort_order=1); Log.Info('[ ] thumbs: "{}"'.format(thumb))
                  episode.thumbs.validate_keys([thumb])
                  Log.Info(u'[ ] Thumb: {}'.format(thumb))
                if Dict(json_video_details, 'snippet',  'channelTitle') and Dict(json_video_details, 'snippet',  'channelTitle') not in [role_obj.name for role_obj in episode.directors]:
                  meta_director = episode.directors.new()
                  meta_director.name = xml_safe(Dict(json_video_details, 'snippet',  'channelTitle'))  # XML-SAFE
                  Log.Info('[ ] director: "{}"'.format(Dict(json_video_details, 'snippet',  'channelTitle')))
                
                for id  in Dict(json_video_details, 'snippet', 'categoryId').split(',') or []:  genre_array[YOUTUBE_CATEGORY_ID[id]] = genre_array[YOUTUBE_CATEGORY_ID[id]]+1 if YOUTUBE_CATEGORY_ID[id] in genre_array else 1
                for tag in Dict(json_video_details, 'snippet', 'tags') or []:  genre_array[tag] = genre_array[tag]+1 if tag in genre_array else 1

              Log.Info(u'[ ] genres: "{}"'.format([x for x in metadata.genres]))  #metadata.genres.clear()
              genre_array_cleansed = [id for id in genre_array if genre_array[id]>episodes/2 and id not in metadata.genres]  #Log.Info('[ ] genre_list: {}'.format(genre_list))
              for id in genre_array_cleansed:  metadata.genres.add(id)
            else:  Log.Info(u'videoId not found in filename')
    
    # Cache-Cleanup für große Bibliotheken
    if episodes > 100:
        cleanup_json_cache()

    # API-Cache-Cleanup (immer durchführen)
    cleanup_api_cache()

  Log('=== End Of Agent Call, errors after that are Plex related ==='.ljust(157, '='))

### Agent declaration ##################################################################################################################################################
class YouTubeSeriesAgent(Agent.TV_Shows):
  name, primary_provider, fallback_agent, contributes_to, accepts_from, languages = 'YouTubeSeries', True, None, None, ['com.plexapp.agents.localmedia'], [Locale.Language.NoLanguage]
  def search (self, results,  media, lang, manual):  Search (results,  media, lang, manual, False)
  def update (self, metadata, media, lang, force ):  Update (metadata, media, lang, force,  False)

class YouTubeMovieAgent(Agent.Movies):
  name, primary_provider, fallback_agent, contributes_to, accepts_from, languages = 'YouTubeMovie', True, None, None, ['com.plexapp.agents.localmedia'], [Locale.Language.NoLanguage]
  def search (self, results,  media, lang, manual):  Search (results,  media, lang, manual, True)
  def update (self, metadata, media, lang, force ):  Update (metadata, media, lang, force,  True)
  
### Variables ###
PluginDir                = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
PlexRoot                 = os.path.abspath(os.path.join(PluginDir, "..", ".."))
CachePath                = os.path.join(PlexRoot, "Plug-in Support", "Data", "com.plexapp.agents.youtube", "DataItems")  # GEÄNDERT: Korrekter Agent-Name
PLEX_LIBRARY             = {}
PLEX_LIBRARY_URL         = "http://127.0.0.1:32400/library/sections/"    # Allow to get the library name to get a log per library https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
YOUTUBE_API_BASE_URL     = "https://www.googleapis.com/youtube/v3/"
YOUTUBE_CHANNEL_ITEMS    = YOUTUBE_API_BASE_URL + 'search?order=date&part=snippet&type=video&maxResults=50&channelId={}&key={}'
YOUTUBE_CHANNEL_DETAILS  = YOUTUBE_API_BASE_URL + 'channels?part=snippet%2CcontentDetails%2Cstatistics%2CbrandingSettings&id={}&key={}'
YOUTUBE_CHANNEL_REGEX    = Regex('\[(?:youtube(|2)\-)?(?P<id>UC[a-zA-Z0-9\-_]{22}|HC[a-zA-Z0-9\-_]{22})\]')
YOUTUBE_PLAYLIST_ITEMS   = YOUTUBE_API_BASE_URL + 'playlistItems?part=snippet,contentDetails&maxResults=50&playlistId={}&key={}'
YOUTUBE_PLAYLIST_DETAILS = YOUTUBE_API_BASE_URL + 'playlists?part=snippet,contentDetails&id={}&key={}'
YOUTUBE_PLAYLIST_REGEX = Regex('\[(?:youtube(|3)\-)?(?P<id>PL[a-zA-Z0-9\-_]{16}|PL[a-zA-Z0-9\-_]{32}|UU[a-zA-Z0-9\-_]{22}|FL[a-zA-Z0-9\-_]{22}|LP[a-zA-Z0-9\-_]{22}|RD[a-zA-Z0-9\-_]{22}|UC[a-zA-Z0-9\-_]{22}|HC[a-zA-Z0-9\-_]{22})\]', Regex.IGNORECASE)  # https://regex101.com/r/37x8wI/2
YOUTUBE_VIDEO_SEARCH     = YOUTUBE_API_BASE_URL + 'search?&maxResults=1&part=snippet&q={}&key={}'
YOUTUBE_json_video_details    = YOUTUBE_API_BASE_URL + 'videos?part=snippet,contentDetails,statistics&id={}&key={}'
YOUTUBE_VIDEO_REGEX = Regex('(?:^\d{8}_|\[(?:youtube\-)?|S1[_\s].*?[_\s](?:\d+p[_\s])?\[)(?P<id>[a-zA-Z0-9\-_]{11})(?:\]|_)', Regex.IGNORECASE)
YOUTUBE_CATEGORY_ID      = {  '1': 'Film & Animation',  '2': 'Autos & Vehicles',  '10': 'Music',          '15': 'Pets & Animals',        '17': 'Sports',                 '18': 'Short Movies',
                             '19': 'Travel & Events',  '20': 'Gaming',            '21': 'Videoblogging',  '22': 'People & Blogs',        '23': 'Comedy',                 '24': 'Entertainment',
                             '25': 'News & Politics',  '26': 'Howto & Style',     '27': 'Education',      '28': 'Science & Technology',  '29': 'Nonprofits & Activism',  '30': 'Movies',
                             '31': 'Anime/Animation',  '32': 'Action/Adventure',  '33': 'Classics',       '34': 'Comedy',                '35': 'Documentary',            '36': 'Drama', 
                             '37': 'Family',           '38': 'Foreign',           '39': 'Horror',         '40': 'Sci-Fi/Fantasy',        '41': 'Thriller',               '42': 'Shorts',
                             '43': 'Shows',            '44': 'Trailers'}

### Plex Library XML ###
Log.Info(u"Library: "+PlexRoot)  #Log.Info(file)
token_file_path = os.path.join(PlexRoot, "X-Plex-Token.id")
if os.path.isfile(token_file_path):
  Log.Info(u"'X-Plex-Token.id' file present")
  token_file=Data.Load(token_file_path)
  if token_file:  PLEX_LIBRARY_URL += "?X-Plex-Token=" + token_file.strip()
  #Log.Info(PLEX_LIBRARY_URL) ##security risk if posting logs with token displayed
try:
  library_xml = etree.fromstring(urllib2.urlopen(PLEX_LIBRARY_URL).read())
  for library in library_xml.iterchildren('Directory'):
    for path in library.iterchildren('Location'):
      PLEX_LIBRARY[path.get("path")] = library.get("title")
      Log.Info(u"{} = {}".format(path.get("path"), library.get("title")))
except Exception as e:  Log.Info(u"Place correct Plex token in {} file or in PLEX_LIBRARY_URL variable in Code/__init__.py to have a log per library - https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token, Error: {}".format(token_file_path, str(e)))
