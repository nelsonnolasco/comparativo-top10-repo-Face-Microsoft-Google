import requests
import datetime
from datetime import timezone
import pandas as pd
from scipy.stats import kruskal
import matplotlib.pyplot as plt

# --- Configurações ---
# Insira seu GitHub Personal Access Token diretamente aqui (escopos: repo, read:org)
GITHUB_TOKEN = 'SEU_TOKEN_AQUI'
if not GITHUB_TOKEN or GITHUB_TOKEN == 'SEU_TOKEN_AQUI':
    raise ValueError("Defina o seu token GitHub diretamente em GITHUB_TOKEN no código.")

# Para chamadas REST e GraphQL do GitHub, use o esquema "token"
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'}

ORGS = ['facebook', 'microsoft', 'google']
TOP_N = 10

# --- Funções de coleta ---
def fetch_top_repos(org, top_n=TOP_N):
    """
    Busca os top-N repositórios mais estrelados de uma organização.
    """
    url = 'https://api.github.com/search/repositories'
    params = {
        'q': f'org:{org}',
        'sort': 'stars',
        'order': 'desc',
        'per_page': top_n
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json().get('items', [])

def count_merged_prs(org, repo_name):
    """
    Conta pull requests fechados (MERGED) via GraphQL.
    """
    url = 'https://api.github.com/graphql'
    query = '''
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        pullRequests(states: MERGED) { totalCount }
      }
    }
    '''
    payload = {'query': query, 'variables': {'owner': org, 'name': repo_name}}
    r = requests.post(url, json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()['data']['repository']['pullRequests']['totalCount']

def count_releases(org, repo_name):
    """
    Conta o número de releases via GraphQL.
    """
    url = 'https://api.github.com/graphql'
    query = '''
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        releases(first: 1) { totalCount }
      }
    }
    '''
    payload = {'query': query, 'variables': {'owner': org, 'name': repo_name}}
    r = requests.post(url, json=payload, headers=HEADERS)
    r.raise_for_status()
    return r.json()['data']['repository']['releases']['totalCount']

# --- Coleta e montagem do DataFrame ---
all_data = []
now = datetime.datetime.now(timezone.utc)

for org in ORGS:
    repos = fetch_top_repos(org)
    for repo in repos:
        name = repo['name']
        created = datetime.datetime.strptime(repo['created_at'], '%Y-%m-%dT%H:%M:%SZ')\
            .replace(tzinfo=timezone.utc)
        updated = datetime.datetime.strptime(repo['updated_at'], '%Y-%m-%dT%H:%M:%SZ')\
            .replace(tzinfo=timezone.utc)
        all_data.append({
            'org': org,
            'repo': name,
            'age_days': (now - created).days,
            'issues': repo.get('open_issues_count', 0),
            'prs_merged': count_merged_prs(org, name),
            'releases': count_releases(org, name),
            'last_update_days': (now - updated).days
        })

df = pd.DataFrame(all_data)

# Salva dados brutos e medianas em CSV
df.to_csv('dados_repos.csv', index=False)
medians = df.groupby('org')[[
    'age_days', 'issues', 'prs_merged', 'releases', 'last_update_days'
]].median()
medians.to_csv('medianas_repos.csv')

# Exibe medianas
print("Medianas dos top-10 repositórios por organização:\n", medians, sep='')

# Gera gráficos de barras para cada métrica
metrics = ['age_days', 'issues', 'prs_merged', 'releases', 'last_update_days']
for metric in metrics:
    plt.figure()
    plt.bar(medians.index, medians[metric])
    plt.ylabel(metric.replace('_', ' ').title())
    plt.title(f'Mediana de {metric.replace("_", " ")} por organização')
    plt.savefig(f'plot_{metric}.png')
    plt.close()

# Testes de Kruskal-Wallis
print("\nResultados dos testes de Kruskal-Wallis:")
for metric in metrics:
    samples = [df[df['org'] == org][metric].dropna().tolist() for org in ORGS]
    H, p = kruskal(*samples)
    print(f"{metric}: H={H:.3f}, p={p:.3f}")

# Hipóteses
print("\nH0: Medianas iguais para Facebook, Microsoft e Google.")
print("H1: Pelo menos uma mediana difere.")
