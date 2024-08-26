import pandas as pd
import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime


# Main functions


def get_teams_from_league(league_url, delay=5):
    """
    Extracts team information from a Fotmob league URL.

    Args:
        league_url (str): The URL of the league page on Fotmob.
        delay (int): The delay (in seconds) between requests to avoid overwhelming the server. Default is 5.

    Returns:
        list: A list of dictionaries containing team details, including team name, ID, logo URL, league name, country, season, and page link.
    """
    teams_dic = []

    # Extract tournament_id and season_id from the URL
    parts = league_url.rstrip('/').split('/')
    leagues_index = parts.index('leagues')
    tournament_id = parts[leagues_index + 1]

    # Build the API URL
    api_url = f'https://www.fotmob.com/api/tltable?leagueId={tournament_id}'

    try:
        # Perform the GET request
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()

        # Extract league information
        league = data[0]['data']['leagueName']
        country = data[0]['data']['ccode']
        season = datetime.now().year

        time.sleep(delay)  # Respect the delay between requests

        # Extract team information
        for i in range(len(data[0]['data']['table']['all'])):
            name = data[0]['data']['table']['all'][i]['name']
            id = data[0]['data']['table']['all'][i]['id']
            logo = f'https://images.fotmob.com/image_resources/logo/teamlogo/{id}_xsmall.png'
            link = 'https://www.fotmob.com/es' + data[0]['data']['table']['all'][i]['pageUrl']

            team_info = {
                'team': name,
                'id': id,
                'logo': logo,
                'league': league,
                'country': country,
                'season': season,
                'link': link
            }

            teams_dic.append(team_info)

    except requests.exceptions.RequestException as e:
        print(f'Error during request: {e}')

    # Export to CSV
    os.makedirs('data', exist_ok=True)
    teams_df = pd.DataFrame(teams_dic)
    teams_df.to_csv('fotmob_teams.csv', index=False, encoding='utf-8')

    return teams_dic


def get_players_from_teams(teams, delay=5):
    """
    Retrieves player information from a list of teams and exports the data to a CSV file.

    Args:
        teams (list): A list of dictionaries where each dictionary contains information about a team.
        delay (int): The number of seconds to wait between requests to avoid overwhelming the server.

    Returns:
        list: A list of dictionaries containing player information.
    """
    players_dic = []  # List to store player information
    repeated = []     # List to keep track of processed player links

    for team in teams:
        time.sleep(delay)  # Respect the delay between requests

        season = team['season']
        league = team['league']
        team_name = team['team']
        url = team['link'].replace('overview', 'squad')
       
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']

            if href not in repeated:
                repeated.append(href)

                if '/es/players/' in href:
                    full_link = 'https://www.fotmob.com' + href
                    player_id = href.rstrip('/').split('/')[-2]
                    profile = f'https://www.fotmob.com/_next/image?url=https%3A%2F%2Fimages.fotmob.com%2Fimage_resources%2Fplayerimages%2F{player_id}.png&w=96&q=75'
                    
                    data = get_player_data(player_id)

                    if data:
                        name = data['name']
                        coach = data['isCoach']

                        player_info = {
                            'name': name,
                            'id': player_id,
                            'profile': profile,
                            'coach': coach,
                            'team': team_name,
                            'league': league,
                            'season': season,
                            'link': full_link
                        }
                        players_dic.append(player_info)
    
    # Export to CSV
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    players_df = pd.DataFrame(players_dic)
    players_df.to_csv('data/fotmob_players.csv', index=False, encoding='utf-8')

    return players_dic


def get_shotmap_from_players(players, delay=5):
    """
    Retrieves shot map data for a list of players and exports the data to a CSV file.

    Args:
        players (list): A list of dictionaries where each dictionary contains information about a player.
        delay (int): The number of seconds to wait between requests to avoid overwhelming the server.

    Returns:
        pd.DataFrame: A DataFrame containing shot map data for all players.
    """
    dfs = []  # List to store DataFrames for each player's shot map data

    for player in players:
        time.sleep(delay)  # Respect the delay between requests

        try:
            player_id = player['id']
            display_season = 0  # Adjust as needed for the actual season ID
            display_league = 0  # Adjust as needed for the actual league ID
            
            # Construct the API URL for the player's shot map data
            api_url = f'https://www.fotmob.com/api/playerStats?playerId={player_id}&seasonId={display_season}-{display_league}&isFirstSeason=false'

            response = requests.get(api_url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
        
            # Convert shot map data to DataFrame
            df = pd.DataFrame(data['shotmap'][0])
            
            # Rename columns and add player info
            df.rename(columns={'playerName': 'player'}, inplace=True)
            df['league'] = player['league']
            df['season'] = player['season']
            df['team'] = player['team']

            # Append DataFrame to the list
            dfs.append(df)
        
        except Exception as e:
            print(f"Error processing player {player['link']}: {e}")
    
    # Export all DataFrames to a CSV file
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    shotmap_df = pd.concat(dfs, ignore_index=True)
    shotmap_df.to_csv('data/fotmob_shotmap.csv', index=False, encoding='utf-8')

    return shotmap_df


def get_positions_from_players(players, delay=5):
    """
    Retrieves position data for a list of players and exports the data to a CSV file.

    Args:
        players (list): A list of dictionaries where each dictionary contains information about a player.
        delay (int): The number of seconds to wait between requests to avoid overwhelming the server.

    Returns:
        pd.DataFrame: A DataFrame containing position data for all players.
    """
    dfs = []  # List to store dictionaries of player position data

    for player in players:
        time.sleep(delay)  # Respect the delay between requests

        player_id = player['id']
        player_name = player['name']
        player_link = player['link']

        data = get_player_data(player_id)

        try:
            if 'positionDescription' in data and 'positions' in data['positionDescription']:
                for position_info in data['positionDescription']['positions']:
                    position = position_info['strPos']['label']
                    pos_short = position_info['strPosShort']['label']
                    pos_id = position_info['position']
                    occurrences = position_info['occurences']
                    main = position_info['isMainPosition']

                    position_dict = {
                        'player_name': player_name,
                        'player_id': player_id,
                        'pos_id': pos_id,
                        'position': position,
                        'pos_short': pos_short,
                        'occurrences': occurrences,
                        'main': main
                    }
                    dfs.append(position_dict)
            else:
                print(f"No positions found for player {player_name} with id {player_id}")

        except Exception as e:
            print(f"Error processing player {player_link} with id {player_id}: {e}")
            print(f"Response data: {data}")

    # Export all DataFrames to a CSV file
    os.makedirs('data', exist_ok=True)  # Create the 'data' directory if it doesn't exist
    positions_df = pd.DataFrame(dfs)
    positions_df.to_csv('data/fotmob_positions.csv', index=False, encoding='utf-8')

    return positions_df


# Support functions


def get_player_data(player_id):
    """
    Fetches player data from Fotmob using the player's ID.

    Args:
        id (int): The ID of the player whose data is to be retrieved.

    Returns:
        dict: A dictionary containing the player's data.
    """
    # Construct the API URL with the player ID
    api_url = f'https://www.fotmob.com/api/playerData?id={player_id}'

    try:
        # Perform the GET request
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Return the JSON response as a dictionary
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f'Error during request: {e}')
        return None
