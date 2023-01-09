import requests
import json
import os
from cairosvg import svg2png
import xmltodict
from time import time, sleep

_query_string = """
SELECT ?label ?code ?flag WHERE {
  ?item wdt:P300 ?code;
        wdt:P41 ?flag;
        wdt:P17/wdt:P30 ?continent FILTER(?continent = wd:Q46).
  ?item rdfs:label ?label FILTER (lang(?label) = "en").
} ORDER BY ?code
"""
query_string="""
SELECT ?item ?itemLabel ?code ?flag WHERE {
  ?item wdt:P297 ?code;
        wdt:P41 ?flag.
  MINUS {
    ?item wdt:P31 wd:Q3024240 .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
} ORDER BY ?itemLabel
"""

url = "https://query.wikidata.org/sparql"

SUBREDDIT = "asklatinamerica"


def fetch_data() -> list:
    print("Fetching wikidata response...")
    response = requests.get(url, params={"query": query_string}, headers={
                            "Accept": "application/sparql-results+json"})
    results_list = json.loads(response.content)['results']['bindings']

    return results_list


headers = {
    'Authorization': f'bearer {os.environ.get("TOKEN")}',
    'Content-Type': 'application/x-www-form-urlencoded',
    'User-agent': "turgid_francis' emoji uploader"
}


def get_s3_lease(result: dict) -> dict:
    response = requests.post(
        url=f"https://oauth.reddit.com/api/v1/{SUBREDDIT}/emoji_asset_upload_s3.json",
        headers=headers,
        data=f"filepath={result['code']['value']}.png&mimetype=image%2Fpng"
    )

    return json.loads(response.content)


def post_file_to_s3(image: bytes, result: dict) -> dict:
    useful_fields = ['acl', 'content-type', 'key', 'policy', 'success_action_status',
                     'X-Amz-Algorithm', 'X-Amz-Credential', 'X-Amz-Date',
                     'x-amz-meta-ext', 'x-amz-security-token', 'X-Amz-Signature', 'x-amz-storage-class']

    post_fields = {f['name']: f['value']
                   for f in result['s3UploadLease']['fields'] if f['name'] in useful_fields}

    response = requests.post(
        f"https:{result['s3UploadLease']['action']}/",
        data=post_fields,
        files={'file': image},
        headers={
            'Origin': 'https://alpha.reddit.com',
            'Referer': f"https://alpha.reddit.com/r/{SUBREDDIT}"
        })

    return xmltodict.parse(response.content)


def post_s3_result_to_reddit(file_name: str, s3_key: str) -> None:
    requests.post(
        url=f"https://oauth.reddit.com/api/v1/{SUBREDDIT}/emoji.json",
        headers=headers,
        data={
            'name': f'flag-{file_name.lower()}',
            's3_key': s3_key,
            'user_flair_allowed': 'true',
            'post_flair_allowed': 'true',
            'mod_flair': 'false'
        }
    )


def upload_flairs_to_reddit(code: str, label: str):
    requests.post(
        url=f"https://oauth.reddit.com/r/{SUBREDDIT}/api/flairtemplate_v2",
        headers=headers,
        data={
            'allowable_content': 'all',
            'api_type': 'json',
            'background_color': 'none',
            'text': f':flag-{code.lower()}: {label}',
            'text_color': '',
            'text_editable': 'false'
        }
    )


results = fetch_data()

index = 0
length = len(results)

print("Uploading emojis to reddit...")

for result in results:
    t1 = time()
    svg_url = result['flag']['value']

    # png_image = svg2png(url=svg_url, output_width=72, output_height=72)

    # s3_lease = get_s3_lease(result)

    # s3_upload_response = post_file_to_s3(png_image, s3_lease)

    # s3_key = s3_upload_response['PostResponse']['Key']

    # post_s3_result_to_reddit(result['code']['value'], s3_key)

    upload_flairs_to_reddit(result['code']['value'], result['itemLabel']['value'])

    print(f"{index}/{length} -- {result['code']['value']}")

    t2 = time()
    diff = t2 - t1

    sleep(max(2 - diff, 0))
    index += 1
