import os
import sys
import inspect
import json
import argparse
import requests

from flask import Flask, render_template, jsonify, request

currentdir = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe()))
)
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from recommendation_lib.rec_util import TopicModel, TranslationRecommender


app = Flask(__name__)


def load_recommenders(data_dir, translation_directions, language_codes):
    model = {}
    directions = json.load(open(translation_directions))
    model['directions'] = directions
    model['codes'] = json.load(open(language_codes))

    for s, ts in directions.items():
        model[s] = {}
        print('Loading Topic Model for: ', s)
        tm = TopicModel(data_dir, s)
        model[s]['topic_model'] = tm
        for t in ts:
            model[s][t] = {}
            print('Loading Recommender for: ', t)
            tr = TranslationRecommender(data_dir, s, t, tm)
            model[s][t]['translation_recommender'] = tr
    print("LOADED MODELS")

    return model


def get_recommender(s, t):

    if s not in model.keys():
        print ("S DOES NOT EXIST")
        return None

    if t not in model[s]:
        print ("T DOES NOT EXIST")
        return None

    return model[s][t]['translation_recommender']


@app.route('/')
def home():
    return render_template(
        'index.html',
        language_pairs=json.dumps(model['directions']),
        language_codes=json.dumps(model['codes'])
    )


def normalize_title(s, title):

    mw_api = 'https://%s.wikipedia.org/w/api.php' % s
    params = {
        'action': 'query', 'format': 'json', 'titles': title, 'redirects': ''
    }
    response = requests.get(mw_api, params=params).json()['query']
    page_id, page_info = list(response['pages'].items())[0]

    if page_id == '-1':
        return title
    else:
        return page_info['title'].replace(' ', '_')


@app.route('/api')
def personal_recommendations():

    if app.debug:
        # add an artificial delay to test UI when in debug mode
        import time
        time.sleep(3)

    s = request.args.get('s')
    t = request.args.get('t')
    article = request.args.get('article')
    n = request.args.get('n')
    try:
        n = int(n)
    except:
        n = 10

    ret = {'articles': []}
    recommender = get_recommender(s, t)

    if recommender:
        if article:
            article = normalize_title(s, article)
            print(article)
            ret['articles'] = recommender.get_seeded_recommendations(
                article, num_recs=n, min_score=0.1
            )
        else:
            ret['articles'] = recommender.get_global_recommendations(
                num_recs=n
            )

    return jsonify(**ret)


parser = argparse.ArgumentParser()
parser.add_argument(
    '--debug', required=False, action="store_true",
    help='run in debug mode'
)
parser.add_argument(
    '--data_dir', required=False, default=os.path.join(parentdir, 'data'),
    help='path to model files'
)
parser.add_argument(
    '--translation_directions', required=False,
    default=os.path.join(parentdir, 'served_translation_directions.json'),
    help='path to json file defining language directions'
)
parser.add_argument(
    '--language-codes', required=False,
    default=os.path.join(parentdir, 'language_codes.json'),
    help='path to json dictionary from language codes to friendly names'
)
args = parser.parse_args()
app.debug = args.debug
model = load_recommenders(
    args.data_dir,
    args.translation_directions,
    args.language_codes
)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
