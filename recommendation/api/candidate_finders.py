import requests
import random
import datetime

from recommendation.api.utils import Article
from recommendation.utils import configuration


class CandidateFinder:
    """
    CandidateFinder interface
    """

    def get_candidates(self, s, seed, n):
        """
        get list candidate source language articles
        using seed (optional)
        """
        return []


class PageviewCandidateFinder(CandidateFinder):
    """
    Utility Class for getting a list of the most
    popular articles in a source  Wikipedia.
    """

    def query_pageviews(self, s):
        """
        Query pageview API and parse results
        """
        days = configuration.get_config_int('popular_pageviews', 'days')
        date_format = configuration.get_config_value('popular_pageviews', 'date_format')
        query = configuration.get_config_value('popular_pageviews', 'query')
        date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).strftime(date_format)
        query = query.format(source=s, date=date)
        try:
            response = requests.get(query)
            response.raise_for_status()
        except requests.RequestException:
            return []
        try:
            data = response.json()
        except ValueError:
            return []

        article_pv_tuples = []

        try:
            for d in data['items'][0]['articles']:
                article_pv_tuples.append((d['article'], d['views']))
        except:
            print("Could not get most popular articles for %s from pageview API. Try using a seed article." % s)

        return article_pv_tuples

    def get_candidates(self, s, seed, n):
        """
        Wrap top articles in a list of Article objects
        """
        articles = []
        article_pv_tuples = sorted(self.query_pageviews(s), key=lambda x: random.random())

        for i, t in enumerate(article_pv_tuples):
            a = Article(t[0])
            a.rank = i
            articles.append(a)

        return articles[:n]


class MorelikeCandidateFinder(CandidateFinder):
    """
    Utility class for getting articles that are similar to
    a given seed article in a source Wikipedia via "morelike"
    search
    """

    def get_morelike_candidates(self, s, query, n):
        """
        Perform a "morelike" search via the Mediawiki search API.
        First map the query to an article via standard search,
        and then get a list of related articles via morelike search
        """
        seed_list = wiki_search(s, query, 1)

        if len(seed_list) == 0:
            print('Seed does not map to an article')
            return []

        seed = seed_list[0]
        if seed != query:
            print('Query: %s  Article: %s' % (query, seed))
        results = wiki_search(s, seed, n, morelike=True)
        if results:
            results.insert(0, seed)
            print('Succesfull Morelike Search')
            return results
        else:
            print('Failed Morelike Search. Reverting to standard search')
            return wiki_search(s, query, n)

    def get_candidates(self, s, seed, n):
        """
        Wrap morelike search results into a list of articles
        """
        results = self.get_morelike_candidates(s, seed, n)

        articles = []

        for i, title in enumerate(results):
            a = Article(title)
            a.rank = i
            articles.append(a)

        return articles[:n]


def wiki_search(s, seed, n, morelike=False):
    """
    A client to the Mediawiki search API
    """
    endpoint, params = build_wiki_search(s, seed, n, morelike)
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
    except requests.RequestException:
        print('Could not search for articles related to seed in %s. Choose another language.' % s)
        return []
    try:
        response = response.json()
    except ValueError:
        return []

    if 'query' not in response or 'search' not in response['query']:
        print('Could not search for articles related to seed in %s. Choose another language.' % s)
        return []

    response = response['query']['search']
    results = [r['title'].replace(' ', '_') for r in response]
    if len(results) == 0:
        print('No articles similar to %s in %s. Try another seed.' % (seed, s))
        return []

    return results


def build_wiki_search(source, seed, count, morelike):
    endpoint = configuration.get_config_value('endpoints', 'wikipedia').format(source=source)
    params = configuration.get_config_dict('wiki_search_params')
    params['srlimit'] = count
    if morelike:
        seed = 'morelike:' + seed
    params['srsearch'] = seed
    return endpoint, params
