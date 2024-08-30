import os
import time
import re
import numpy as np
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from io import StringIO

# Main functions


def get_teams_from_league(league_url):
    """
    Retrieves team information from a league page and exports the data to a CSV file.

    Args:
        league_url (str): The URL of the league page on FBref.

    Returns:
        list: A list of dictionaries, each containing information about a team.
    """
    teams_dic = []  # List to store team information
    repeated = []  # List to keep track of processed links

    # Extract league_id and season from the URL
    parts = league_url.rstrip('/').split('/')
    league_id = parts[-2]
    season = datetime.now().year
    final = parts[-1].rstrip('-').replace('Estadisticas-de-', '').split('-')
    league = f'{final[-3]} {final[-2]}'
    country = final[-1]

    # Get the HTML page
    response = requests.get(league_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the specific container by its ID
    table_container = soup.find('div', id='div_results2024211_overall')

    if table_container:
        links = table_container.find_all('a', href=True)  # Find all links within the container

        for link in links:
            href = link['href']

            if href not in repeated:
                repeated.append(href)

                if '/es/equipos/' in href:
                    team_name = href.rstrip('/').split('/')[-1].replace('Estadisticas-de-', '').replace('-', ' ')
                    team_id = href.rstrip('/').split('/')[-2]
                    full_link = 'https://www.fbref.com' + href

                    teams_info = {
                        'name': team_name,
                        'id': team_id,
                        'logo': f'https://cdn.ssref.net/req/202408052/tlogo/fb/{team_id}.png',
                        'league': league,
                        'league_id': league_id,
                        'country': country,
                        'season': season,
                        'link': full_link
                    }

                    teams_dic.append(teams_info)

    # Export to CSV
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    teams_df = pd.DataFrame(teams_dic)
    teams_df.to_csv('data/fbref_teams.csv', index=False, encoding='utf-8')

    return teams_dic


def get_standings_from_league(league_url):
    """
    Retrieves the standings table from the given league URL and exports the data to a CSV file.

    Args:
        league_url (str): The URL of the league standings page.

    Returns:
        pd.DataFrame: A DataFrame containing the standings data, or None if an error occurs.
    """
    parts = league_url.rstrip('/').split('/')
    league_id = parts[-2]
    season = datetime.now().year
    final = parts[-1].rstrip('-').replace('Estadisticas-de-', '').split('-')
    league = f'{final[-3]} {final[-2]}'
    country = final[-1]
    
    try:
        # Read the standings table from the specified URL with the given ID
        standings_df = pd.read_html(league_url, attrs={'id': f'results{season}{league_id}1_overall'})[0]
        
        standings_df['league'] = league
        standings_df['season'] = season
        standings_df['country'] = country

        standings_df.rename(columns={'Equipo': 'team'}, inplace=True)
    
        # Export to CSV
        os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
        standings_df.to_csv('data/fbref_standings.csv', index=False, encoding='utf-8')

        return standings_df

    except Exception as e:
        print(f"Error processing ID {league_id} for league {league_url}: {e}")
        return


def get_stats_from_league(league_url, delay=10):
    """
    Retrieves various statistics from a league URL and exports the data to a CSV file.

    Args:
        league_url (str): URL of the league page containing the statistics tables.
        delay (int): Delay in seconds between requests to avoid hitting rate limits.

    Returns:
        pd.DataFrame: A DataFrame containing all the statistics data.
    """
    parts = league_url.rstrip('/').split('/')
    league_id = parts[-2]
    season = datetime.now().year
    final = parts[-1].rstrip('-').replace('Estadisticas-de-', '').split('-')
    league = f'{final[-3]} {final[-2]}'
    country = final[-1]

    # List of table IDs to scrape
    table_ids = (
        'stats_squads_standard_for', 'stats_squads_standard_against',
        'stats_squads_keeper_for', 'stats_squads_keeper_against',
        'stats_squads_keeper_adv_for', 'stats_squads_keeper_adv_against',
        'stats_squads_shooting_for', 'stats_squads_shooting_against',
        'stats_squads_passing_for', 'stats_squads_passing_against',
        'stats_squads_passing_types_for', 'stats_squads_passing_types_against',
        'stats_squads_gca_for', 'stats_squads_gca_against',
        'stats_squads_defense_for', 'stats_squads_defense_against',
        'stats_squads_possession_for', 'stats_squads_possession_against',
        'stats_squads_playing_time_for', 'stats_squads_playing_time_against',
        'stats_squads_misc_for', 'stats_squads_misc_against'
    )

    dfs = []

    for table_id in table_ids:
        time.sleep(delay)  # Respect the delay between requests
        
        try:
            # Read the table from the URL using the ID
            df = pd.read_html(league_url, attrs={'id': table_id})[0]

            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ['_'.join(col).strip() if 'Unnamed' not in col[0] else col[1] for col in df.columns]

            # Melt the DataFrame to long format
            df_pivot = df.melt(id_vars=['Equipo'], var_name='stat', value_name='value')

            # Split 'stat' into 'class' and 'stat' if applicable
            if df_pivot['stat'].str.contains('_').any():
                df_pivot[['class', 'stat']] = df_pivot['stat'].str.split('_', expand=True, n=1)
            else:
                df_pivot['stat'] = ''
                df_pivot['class'] = df_pivot['stat']

            # Update 'stat' and 'class' columns
            df_pivot['stat'] = df_pivot.apply(lambda row: row['class'] if pd.isna(row['stat']) else row['stat'], axis=1)
            df_pivot['class'] = df_pivot.apply(lambda row: np.nan if row['stat'] == row['class'] else row['class'], axis=1)

            # Extract table name and target ('for' or 'against')
            table_match = re.match(r'(.+)(_for|_against)', table_id)
            table_name = re.sub(r'stats_squads_', '', table_match.group(1)) if table_match else ''
            table_name = table_name.replace('_', ' ').title()

            df_pivot['table'] = table_name
            df_pivot['target'] = 'for' if '_for' in table_id else 'against' if '_against' in table_id else None
            df_pivot['target'] = df_pivot['target'].str.title()
            df_pivot['league'] = league
            df_pivot['country'] = country
            df_pivot['season'] = season
            df_pivot.rename(columns={'Equipo': 'team'}, inplace=True)
            
            # Append the DataFrame to the list
            dfs.append(df_pivot)

        except Exception as e:
            print(f"Error processing ID {table_id}: {e}")

    # Combine all DataFrames and export to CSV
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    stats_df = pd.concat(dfs, ignore_index=True)
    stats_df.to_csv('data/fbref_stats.csv', index=False, encoding='utf-8')

    return stats_df


def get_players_from_teams(teams, delay=10):
    """
    Retrieves player information from each team in the provided list and exports the data to a CSV file.

    Args:
        teams (list): A list of dictionaries, each containing information about a team.
        delay (int): Delay in seconds between requests to avoid hitting rate limits.

    Returns:
        list: A list of dictionaries, each containing information about a player.
    """
    players_dic = []  # List to store player information
    repeated = []  # List to keep track of processed links

    for team in teams:
        time.sleep(delay)  # Respect the delay between requests

        # Extract team information
        team_name = team['name']
        season = team['season']
        league = team['league']
        country = team['country']

        # Get the HTML page for the team's players
        response = requests.get(team['link'])
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the specific container by its ID
        table_container = soup.find('div', id='all_stats_standard')

        if table_container:
            links = table_container.find_all('a', href=True)  # Find all links within the container

            for link in links:
                href = link['href']

                if href not in repeated and 'summary' not in href:  # Exclude links containing 'summary'
                    repeated.append(href)

                    if '/es/jugadores/' in href:
                        player_name = href.rstrip('/').split('/')[-1].replace('-', ' ')
                        player_id = href.rstrip('/').split('/')[-2]
                        full_link = 'https://www.fbref.com' + href

                        players_info = {
                            'player': player_name,
                            'id': player_id,
                            'profile': f'https://fbref.com/req/202302030/images/headshots/{player_id}_2022.jpg',
                            'team': team_name,
                            'league': league,
                            'season': season,
                            'country': country,
                            'link': full_link
                        }

                        players_dic.append(players_info)

    # Export to CSV
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    players_df = pd.DataFrame(players_dic)
    players_df.to_csv('data/fbref_players.csv', index=False, encoding='utf-8')

    return players_dic


def get_squads_from_teams(teams, delay=10):
    """
    Retrieves the squad information from the given teams' URLs and exports the data to a CSV file.

    Args:
        teams (list of dict): A list of dictionaries containing team information with keys such as 'name', 'season', 'league', 'country', and 'link'.
        delay (int): The delay in seconds between requests to avoid overloading the server.

    Returns:
        pd.DataFrame: A DataFrame containing the combined squad data for all teams.
    """
    dfs = []

    for team in teams:
        time.sleep(delay)  # Respect delay between requests

        season = team['season']
        league = team['league']
        country = team['country']
        id = 'stats_standard_' + team['league_id']

        try:
            # Read the squad table from the specified URL with the given ID
            df = pd.read_html(team['link'], attrs={'id': id})[0]

            df.columns = df.columns.get_level_values(1)

            # Process the 'Edad' column to convert age ranges to average age in years
            df['Edad'] = df['Edad'].apply(
                lambda x: float(x.rstrip('-').split('-')[0]) + float(x.rstrip('-').split('-')[1])/365
                if isinstance(x, str) and '-' in x else x
            )
            df['Edad'] = pd.to_numeric(df['Edad'], errors='coerce')

            # Drop rows with NaN values in the 'Edad' column
            squad_df = df.dropna(subset=['Edad']).copy()

            # Extract the last 3 characters from the 'País' column to get the country code
            squad_df['País'] = squad_df['País'].apply(lambda x: str(x)[-3:])

            # Rename columns and add additional team information
            squad_df.rename(columns={'Jugador': 'player'}, inplace=True)
            squad_df['league'] = league
            squad_df['season'] = season
            squad_df['team'] = team['name']
            squad_df['country'] = country

            dfs.append(squad_df)

        except Exception as e:
            print(f"Error processing team {team['name']} at {team['link']}: {e}")

    # Export all DataFrames to a CSV file
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    squads_df = pd.concat(dfs, ignore_index=True)
    squads_df.to_csv('data/fbref_squads.csv', index=False, encoding='utf-8')

    return squads_df


def get_percentile_from_players(players, delay=10, language='ES'):
    """
    Retrieves percentile statistics for a list of players and exports the data to a CSV file.

    Args:
        players (list of dict): A list of dictionaries containing player information with keys such as 'player', 'id', and 'link'.
        delay (int): The delay in seconds between requests to avoid overloading the server.
        language (str): The language for the percentile category labels ('ES' for Spanish, English in any other case).

    Returns:
        pd.DataFrame: A DataFrame containing the combined percentile data for all players.
    """
    dfs = []

    for player in players:
        time.sleep(delay)  # Respect delay between requests

        try:
            # Retrieve the content of the player's page
            response = requests.get(player['link'])
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find the table with an id that starts with 'scout_summary_'
            table = soup.find('table', id=lambda x: x and x.startswith('scout_summary_'))

            if table:
                # Read the table into a DataFrame
                df = pd.read_html(StringIO(str(table)))[0]

                # Determine the bins and labels based on the statistics type
                if df.loc[0, 'Estadísticas'] == 'PSxG-GA':
                    bins = [0, 6, 11, 15]
                    if language == 'ES':
                        labels = ['Portería', 'Colectiva', 'Defensiva']
                    else:
                        labels = ['Keeper', 'Passing', 'Defensive']
                else:
                    bins = [0, 7, 15, 21]
                    if language == 'ES':
                        labels = ['Ofensiva', 'Colectiva', 'Defensiva']
                    else:
                        labels = ['Offensive', 'Passing', 'Defensive']

                # Clean the DataFrame
                df = df.dropna(how='all')
                df['player'] = player['player']
                df['player_id'] = player['id']

                # Create a column with category labels based on the bins
                df['clase'] = pd.cut(df.index, bins=bins, labels=labels, right=False)

                dfs.append(df)
            
        except Exception as e:
            print(f"Error processing player {player['player']} at {player['link']}: {e}")

    # Export all DataFrames to a CSV file
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    percentiles_df = pd.concat(dfs, ignore_index=True)
    percentiles_df.to_csv('data/fbref_percentiles.csv', index=False, encoding='utf-8')

    return percentiles_df
