import pandas as pd
import re
import requests
import time
import os
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# Main functions


def get_teams_from_league(league_url):
    """
    Extracts team information from a Sofascore league URL.

    Args:
        league_url (str): The URL of the league page on Sofascore.

    Returns:
        list: A list of dictionaries containing team details, including name, ID, logo, league, country, season, and link.
    """
    teams_dic = []
    seen_links = []
    j = 0

    # Extract tournament_id and season_id from the URL
    parts = league_url.rstrip('/').split('/')
    tournament_id = parts[-1].split('#id:')[0]
    season_id = parts[-1].split('#id:')[1]

    # Use the get_tournament_standing function to get league data
    standings = get_tournament_standing(tournament_id, season_id)
    if standings is None:
        return teams_dic

    league = standings['league']
    country = standings['country']
    season = standings['season']
    teams_name = standings['teams_name']
    teams_id = standings['teams_id']

    try:
        response = requests.get(league_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']

            if href not in seen_links:
                seen_links.append(href)

                if '/es/equipo/futbol/' in href:
                    full_link = 'https://www.sofascore.com' + href

                    if j < len(teams_name):
                        team_info = {
                            'team': teams_name[j],
                            'id': teams_id[j],
                            'logo': f'https://api.sofascore.app/api/v1/team/{teams_id[j]}/image',
                            'league': league,
                            'country': country,
                            'season': season,
                            'link': full_link
                        }
                        teams_dic.append(team_info)
                        j += 1

    except requests.exceptions.RequestException as e:
        print(f'Error during request: {e}')
    
    # Export to CSV
    os.makedirs('data', exist_ok=True)
    teams_df = pd.DataFrame(teams_dic)
    teams_df.to_csv('data/sofascore_teams.csv', index=False, encoding='utf-8')

    return teams_dic


def get_events_from_league(league_url):
    """
    Extracts event results from a Sofascore league URL.

    Args:
        league_url (str): The URL of the league page on Sofascore.

    Returns:
        list: A list of dictionaries containing event details, including round number, season, and link.
    """
    if not league_url.endswith(',tab:matches'):
        league_url += ',tab:matches'
    
    # Set up the driver
    driver = webdriver.Chrome()  # Or use `webdriver.Firefox()` if you are using Firefox
    events_dic = []  # List to store each event result as a separate row
    
    try:
        # Go to the URL
        driver.get(league_url)

        # Wait for the "By Rounds" tab to be clickable and click it
        wait = WebDriverWait(driver, 30)
        rounds_tab = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-tabid="2"]')))
        rounds_tab.click()

        # Wait for the content of the "By Rounds" tab to load
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="event_cell"]')))

        # Get the season text
        season_element = driver.find_element(By.CSS_SELECTOR, 'div.Box.Flex.eJCdjm.bnpRyo .Text.nZQAT')
        season_text = season_element.text
        
        # Extract the season number from the text
        season = season_text.split(' ')[-1]  # Get the last element after the space

        # Initialize variables
        round_number = None
        
        while True:
            # Get the round text
            round_container = driver.find_element(By.CSS_SELECTOR, 'div.Box.gRmPLj')
            round_items = round_container.find_elements(By.CSS_SELECTOR, 'div.Text.nZQAT')
            
            selected_round = None
            for item in round_items:
                round_text = item.text
                if 'Round' or 'Ronda' in round_text:
                    selected_round = round_text
                    break

            # Extract the round number from the text
            current_round_number = selected_round.split(' ')[-1] if selected_round else 'Not found'
            
            if current_round_number == 'Not found':
                break
            
            round_number = int(current_round_number)
            
            # Extract event links for the current round
            event_cells = driver.find_elements(By.CSS_SELECTOR, '[data-testid="event_cell"]')
            for cell in event_cells:
                href = cell.get_attribute('href')
                if href and 'summary' not in href:  # Exclude links containing 'summary'
                    
                    # Extract tournament information
                    event_id = re.search(r'#id:(\d+)', href).group(1)
                    data = get_event_data(event_id)
                    league = data['event']['tournament']['name']
                    league_id = data['event']['tournament']['uniqueTournament']['id']
                    season_id = data['event']['season']['id']
                    country = data['event']['tournament']['category']['name']
                    home_team_id = data['event']['homeTeam']['id']
                    away_team_id = data['event']['awayTeam']['id']

                    round_result = {
                        'id': event_id,
                        'league': league,
                        'league_id': league_id,
                        'country': country,
                        'round': round_number,
                        'season': season,
                        'season_id': season_id,
                        'home_team_id': home_team_id,
                        'away_team_id': away_team_id,
                        'link': href
                    }

                    events_dic.append(round_result)

            # Check if we have reached round 1 and exit the loop if so
            if round_number <= 1:
                break

            # Try to go to the previous round
            try:
                previous_round_button = driver.find_element(By.CSS_SELECTOR, 'button.Button.iCnTrv')
                previous_round_button.click()
                # Wait a moment for the page to load
                WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="event_cell"]')))
            except Exception as e:
                print(f"Error navigating to previous round: {e}")
                break

    finally:
        # Close the browser
        driver.quit()
    
    # Export to CSV
    os.makedirs('data', exist_ok=True)
    events_df = pd.DataFrame(events_dic)
    events_df.to_csv('data/sofascore_events.csv', index=False, encoding='utf-8')

    return events_dic


def get_players_from_teams(teams, delay=5):
    """
    Extracts player information from team URLs on Sofascore.

    Args:
        teams (list): List of dictionaries, each containing team details and URL.
        delay (int): Time to wait (in seconds) between requests to avoid overloading the server. Default is 5 seconds.

    Returns:
        list: A list of dictionaries with player information.
    """
    players_dic = []  # List to store player information
    repeated = []  # List to keep track of processed links

    for team in teams:
        time.sleep(delay)  # Respect the delay between requests

        team_name = team['team']
        season = team['season']
        league = team['league']
        country = team['country']
        url = team['link']

        # Make the request and parse the page content
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']

            if href not in repeated:
                repeated.append(href)

                if '/es/jugador/' in href:
                    full_link = 'https://www.sofascore.com' + href
                    id = href.rstrip('/').split('/')[-1]
                    name = href.rstrip('/').split('/')[-2].replace('-', ' ').title()
                    profile = f'https://api.sofascore.app/api/v1/player/{id}/image'

                    # Create a dictionary for the player
                    player_info = {
                        'name': name,
                        'id': id,
                        'profile': profile,
                        'team': team_name,
                        'league': league,
                        'country': country,
                        'season': season,
                        'link': full_link
                    }
                    players_dic.append(player_info)

    # Export to CSV
    os.makedirs('data', exist_ok=True)
    players_df = pd.DataFrame(players_dic)
    players_df.to_csv('data/sofascore_players.csv', index=False, encoding='utf-8')

    return players_dic


def get_heatmap_from_players(players, delay=5):
    """
    Fetches heatmap data for a list of players from Sofascore API.

    Args:
        players (list of dict): List of player dictionaries with 'player_id'.
        delay (int): Delay in seconds between API requests to avoid rate limiting.

    Returns:
        DataFrame: Combined heatmap data for all players and tournaments.
    """
    
    dfs = []

    for player in players:
        time.sleep(delay)
        player_id = player['id']
        
        # Get tournaments for the current player
        try:
            tournaments = get_player_tournaments(player_id)
        except:
            continue
        
        # Loop through each tournament
        for _, row in tournaments.iterrows():
            league_id = row['tournaments_id']
            season_id = row['season_id']

            # Get heatmap for the current player, league, and season
            try:
                heatmap_tournament = get_heatmap(player_id, league_id, season_id)
                dfs.append(heatmap_tournament)
            except:
                continue

    # Concatenate all dataframes and save to CSV
    if dfs:
        os.makedirs('data', exist_ok=True)
        heatmaps_df = pd.concat(dfs, ignore_index=True)
        heatmaps_df.to_csv('data/sofascore_heatmap.csv', index=False, encoding='utf-8')
    else:
        heatmaps_df = pd.DataFrame()
        print("No heatmap data was collected.")

    return heatmaps_df


def get_lineups_from_events(events, delay=5):
    """
    Processes a list of events to extract and organize lineup data and average player positions.

    Args:
        events (list): List of dictionaries containing event information.
        delay (int): Time to wait (in seconds) between requests to avoid overloading the server. Default is 5 seconds.

    Returns:
        pd.DataFrame: A DataFrame containing the lineup data and average player positions for all processed events.
    """
    dfs = []  # Initialize a list to store DataFrames for each event

    for i in range(len(events)):
        time.sleep(delay)  # Wait before making the next request

        event = re.search(r'id:(\d+)', events[i]['link'])
        event_id = event.group(1) if event else 'unknown'
        
        try:
            data = get_event_data(event_id)
            status = data['event']['status']['type']

            if status == 'finished':
                # Get lineup, average positions, and event data
                lineups = get_lineups(event_id)
                average_positions = get_average_positions(event_id)

                # Extract and process formations for home and away teams
                home_formation = lineups['home']['formation']
                away_formation = lineups['away']['formation']

                # Process home formation
                home_groups_formation = home_formation.split('-')
                home_def = int(home_groups_formation[0])
                home_ata = int(home_groups_formation[-1])

                if len(home_groups_formation) == 4:
                    home_mid_0 = int(home_groups_formation[1])
                    home_mid_1 = 0
                    home_mid_2 = int(home_groups_formation[2])
                else:
                    home_mid_0 = 0
                    home_mid_1 = int(home_groups_formation[1])
                    home_mid_2 = 0

                # Process away formation
                away_groups_formation = away_formation.split('-')
                away_def = int(away_groups_formation[0])
                away_ata = int(away_groups_formation[-1])

                if len(away_groups_formation) == 4:
                    away_mid_0 = int(away_groups_formation[1])
                    away_mid_1 = 0
                    away_mid_2 = int(away_groups_formation[2])
                else:
                    away_mid_0 = 0
                    away_mid_1 = int(away_groups_formation[1])
                    away_mid_2 = 0

                # Initialize lists to store player data
                home = []
                away = []
                home_avg = []
                away_avg = []

                # Process home team players
                for j in range(len(lineups['home']['players'])):
                    player = lineups['home']['players'][j]
                    name = player['player']['name']
                    id = player['player']['id']
                    jersey = player['shirtNumber']
                    position = player.get('position', '')
                    substitute = player['substitute']
                    minutes = player.get('statistics', {}).get('minutesPlayed', 0)

                    if j < len(average_positions['home']):
                        avg_player = average_positions['home'][j]
                        avg_id = avg_player['player']['id']
                        averageX = avg_player['averageX']
                        averageY = avg_player['averageY']
                        pointsCount = avg_player['pointsCount']

                    order = j + 1
                    line, lat, pos = determine_position(order, home_def, home_mid_0, home_mid_1, home_mid_2, home_ata, substitute)
                    
                    # Append player data to home list
                    home.append([name, id, jersey, position, substitute, minutes, order, line, lat, pos])
                    home_avg.append([avg_id, averageX, averageY, pointsCount])

                # Process away team players
                for k in range(len(lineups['away']['players'])):
                    player = lineups['away']['players'][k]
                    name = player['player']['name']
                    id = player['player']['id']
                    jersey = player['shirtNumber']
                    position = player.get('position', '')
                    substitute = player['substitute']
                    minutes = player.get('statistics', {}).get('minutesPlayed', 0)

                    if k < len(average_positions['away']):
                        avg_player = average_positions['away'][k]
                        avg_id = avg_player['player']['id']
                        averageX = avg_player['averageX']
                        averageY = avg_player['averageY']
                        pointsCount = avg_player['pointsCount']

                    order = k + 1
                    line, lat, pos = determine_position(order, away_def, away_mid_0, away_mid_1, away_mid_2, away_ata, substitute)

                    # Append player data to away list
                    away.append([name, id, jersey, position, substitute, minutes, order, line, lat, pos])
                    away_avg.append([avg_id, averageX, averageY, pointsCount])

                # Create DataFrames for home and away teams
                home_df = pd.DataFrame(home, columns=['player', 'id', 'jersey', 'position', 'substitute', 'minutes', 'order', 'line', 'lat', 'pos'])
                home_df['local'] = 'Home'
                home_df['team'] = data['event']['homeTeam']['shortName']
                home_df['formation'] = home_formation
                home_df['defense'] = home_def
                home_df['midfield'] = home_mid_0 + home_mid_1 + home_mid_2
                home_df['attack'] = home_ata

                away_df = pd.DataFrame(away, columns=['player', 'id', 'jersey', 'position', 'substitute', 'minutes', 'order', 'line', 'lat', 'pos'])
                away_df['local'] = 'Away'
                away_df['team'] = data['event']['awayTeam']['shortName']
                away_df['formation'] = away_formation
                away_df['defense'] = away_def
                away_df['midfield'] = away_mid_0 + away_mid_1 + away_mid_2
                away_df['attack'] = away_ata

                # Create DataFrame for average player positions
                home_avg_position = pd.DataFrame(home_avg, columns=['avg_id', 'averageX', 'averageY', 'pointsCount'])
                away_avg_position = pd.DataFrame(away_avg, columns=['avg_id', 'averageX', 'averageY', 'pointsCount'])
                df_avg_position = pd.concat([home_avg_position, away_avg_position], ignore_index=True)
                df_avg_position.rename(columns={'avg_id': 'id'}, inplace=True)

                # Merge lineup data with average position data
                df = pd.concat([home_df, away_df], ignore_index=True)
                df_merged = pd.merge(df, df_avg_position, on='id', how='left')

                # Append the DataFrame to the list
                dfs.append(df_merged)

        except Exception as e:
            print(f"Error in processing lineup for event {event_id}: {e}")

    # Concatenate all DataFrames into one and save to CSV
    os.makedirs('data', exist_ok=True)
    lineups_df = pd.concat(dfs, ignore_index=True)
    lineups_df.to_csv('data/sofascore_lineup.csv', index=False, encoding='utf-8')

    return lineups_df


def get_results_from_events(events, delay=5):
    """
    Extracts match results from a list of events and returns a DataFrame.

    Args:
        events (list): A list of event dictionaries, each containing an 'id'.
        delay (int, optional): Delay in seconds between requests. Default is 5 seconds.

    Returns:
        pd.DataFrame: A DataFrame containing match results for each event.
    """
    # List to store DataFrames for each event
    dfs = []

    for event in events:
        # Respect the delay between requests to avoid overloading the server
        time.sleep(delay)

        # Extract the event ID from the event dictionary
        event_id = event['id']

        # Fetch event data using the event ID
        event_data = get_event_data(event_id)
        status = event_data['event']['status']['type']

        if status == 'finished':
            # Extract necessary details from the event data
            homeTeam_name = event_data['event']['homeTeam']['shortName']
            homeTeam_id = event_data['event']['homeTeam']['id']
            homeScore = int(event_data['event']['homeScore']['display'])
            awayTeam_name = event_data['event']['awayTeam']['shortName']
            awayTeam_id = event_data['event']['awayTeam']['id']
            awayScore = int(event_data['event']['awayScore']['display'])

            # Create a dictionary for the home team
            home_dic = {
                'event_id': event_id,
                'team': homeTeam_name,
                'team_id': homeTeam_id,
                'score_for': homeScore,
                'score_against': awayScore,
                'win': homeScore > awayScore,
                'draw': homeScore == awayScore,
                'loose': homeScore < awayScore,
                'local': 'Home'
            }

            # Create a dictionary for the away team
            away_dic = {
                'event_id': event_id,
                'team': awayTeam_name,
                'team_id': awayTeam_id,
                'score_for': awayScore,
                'score_against': homeScore,
                'win': awayScore > homeScore,
                'draw': awayScore == homeScore,
                'loose': awayScore < homeScore,
                'local': 'Away'
            }

            # Convert the dictionaries into DataFrames
            home_df = pd.DataFrame([home_dic])
            away_df = pd.DataFrame([away_dic])

            # Concatenate the home and away DataFrames into a single DataFrame
            df = pd.concat([home_df, away_df], ignore_index=True)

            # Append the DataFrame to the list
            dfs.append(df)

    # Concatenate all the DataFrames into one final DataFrame
    results_df = pd.concat(dfs, ignore_index=True)

    # Export the final DataFrame to a CSV file
    os.makedirs('data', exist_ok=True)
    results_df.to_csv('data/sofascore_results.csv', index=False, encoding='utf-8')

    return results_df


# Support functions


def determine_position(order, def_count, mid_0_count, mid_1_count, mid_2_count, ata_count, substitute):
    """
    Determines the position, line, and latitude of a player based on their order in the lineup.

    Args:
        order (int): Player's order in the lineup.
        def_count (int): Number of defenders.
        mid_0_count (int): Number of midfielders in the first group.
        mid_1_count (int): Number of midfielders in the second group.
        mid_2_count (int): Number of midfielders in the third group.
        ata_count (int): Number of attackers.
        substitute (bool): Whether the player is a substitute.

    Returns:
        tuple: (line, latitude, position)
    """
    home_por = 1
    
    if order == home_por:
        line = 'por'
        lat = '1/1'
        pos = 'POR'
    elif order <= home_por + def_count:
        line = 'def'
        lat = f'{order - home_por}/{def_count}'
        pos = 'DEF'
    elif order <= home_por + def_count + mid_0_count:
        line = 'mid_0'
        lat = f'{order - home_por - def_count}/{mid_0_count}'
        pos = 'MED'
    elif order <= home_por + def_count + mid_0_count + mid_1_count:
        line = 'mid_1'
        lat = f'{order - home_por - def_count - mid_0_count}/{mid_1_count}'
        pos = 'MED'
    elif order <= home_por + def_count + mid_0_count + mid_1_count + mid_2_count:
        line = 'mid_2'
        lat = f'{order - home_por - def_count - mid_0_count - mid_1_count}/{mid_2_count}'
        pos = 'MED'
    elif order <= home_por + def_count + mid_0_count + mid_1_count + mid_2_count + ata_count:
        line = 'ata'
        lat = f'{order - home_por - def_count - mid_0_count - mid_1_count - mid_2_count}/{ata_count}'
        pos = 'ATA'
    elif order > 11 and substitute:
        line = None
        lat = None
        pos = 'SUS'
    elif order > 11 and not substitute:
        line = None
        lat = None
        pos = 'RES'
    else:
        line = None
        lat = None
        pos = None

    return line, lat, pos


def create_team_df(players, formation, def_count, mid_0_count, mid_1_count, mid_2_count, ata_count, team_name, is_home):
    """
    Creates a DataFrame for a team based on players' data and formation.

    Args:
        players (list): List of player dictionaries with their details.
        formation (str): Team formation in 'def-mid-ata' format.
        def_count (int): Number of defenders.
        mid_0_count (int): Number of midfielders in the first group.
        mid_1_count (int): Number of midfielders in the second group.
        mid_2_count (int): Number of midfielders in the third group.
        ata_count (int): Number of attackers.
        team_name (str): Name of the team.
        is_home (bool): Whether the team is the home team.

    Returns:
        pd.DataFrame: DataFrame containing player details and team information.
    """
    team_data = []
    for j, player in enumerate(players):
        name = player['player']['name']
        id = player['player']['id']
        jersey = player['shirtNumber']
        position = player.get('position', '')
        substitute = player['substitute']
        minutes = player.get('statistics', {}).get('minutesPlayed', 0)
        
        order = j + 1
        line, lat, pos = determine_position(order, def_count, mid_0_count, mid_1_count, mid_2_count, ata_count, substitute)

        team_data.append([name, id, jersey, position, substitute, minutes, order, line, lat, pos])

    df = pd.DataFrame(team_data, columns=['player', 'id', 'jersey', 'position', 'substitute', 'minutes', 'order', 'line', 'lat', 'pos'])
    df['team'] = team_name
    df['formation'] = formation
    df['defense'] = def_count
    df['midfield'] = mid_0_count + mid_1_count + mid_2_count
    df['attack'] = ata_count
    df['local'] = 'Home' if is_home else 'Away'
    
    return df


def get_lineups(event_id):
    """
    Retrieves the lineups for a given event from Sofascore.

    Parameters:
        event_id (int): The unique identifier for the event.

    Returns:
        dict: The JSON response containing lineup information.
    """
    api_url = f'https://www.sofascore.com/api/v1/event/{event_id}/lineups'
    response = requests.get(api_url)
    response.raise_for_status()  # Ensure we raise an error for bad responses
    return response.json()


def get_average_positions(event_id):
    """
    Retrieves the average positions for players in a given event from Sofascore.

    Parameters:
        event_id (int): The unique identifier for the event.

    Returns:
        dict: The JSON response containing average position information.
    """
    api_url = f'https://www.sofascore.com/api/v1/event/{event_id}/average-positions'
    response = requests.get(api_url)
    response.raise_for_status()  # Ensure we raise an error for bad responses
    return response.json()


def get_event_data(event_id):
    """
    Retrieves general data for a given event from Sofascore.

    Parameters:
        event_id (int): The unique identifier for the event.

    Returns:
        dict: The JSON response containing event data.
    """
    api_url = f'https://www.sofascore.com/api/v1/event/{event_id}'
    response = requests.get(api_url)
    response.raise_for_status()  # Ensure we raise an error for bad responses
    return response.json()


def get_tournament_standing(tournament_id, season_id):
    """
    Fetches the standings of a specific tournament and season from Sofascore.

    Args:
        tournament_id (str): The unique identifier for the tournament.
        season_id (str): The unique identifier for the season.

    Returns:
        dict: A dictionary containing league, country, season, team names, and team IDs.
    """
    api_url = f'https://www.sofascore.com/api/v1/unique-tournament/{tournament_id}/season/{season_id}/standings/total'

    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()

        league = data['standings'][0]['tournament']['name']
        country = data['standings'][0]['tournament']['category']['name']
        season = datetime.fromtimestamp(data['standings'][0]['updatedAtTimestamp']).year

        teams_name = [row['team']['name'] for row in data['standings'][0]['rows']]
        teams_id = [row['team']['id'] for row in data['standings'][0]['rows']]

        return {
            'league': league,
            'country': country,
            'season': season,
            'teams_name': teams_name,
            'teams_id': teams_id
        }

    except requests.exceptions.RequestException as e:
        print(f'Error fetching tournament standings: {e}')
        return None
    

def get_player_tournaments(player_id):
    """
    Fetches the tournaments and seasons a player has participated in from the Sofascore API.

    Args:
        player_id (int): The unique identifier for the player in Sofascore.

    Returns:
        DataFrame: A pandas DataFrame containing tournament and season information for the player.
    """
    
    tournaments = []
    api_url = f'https://www.sofascore.com/api/v1/player/{player_id}/statistics/seasons'
    
    response = requests.get(api_url)
    response.raise_for_status()
    data = response.json()

    current_year = str(datetime.now().year)
    
    # Loop through each tournament and its seasons in the JSON data
    for tournament in data['uniqueTournamentSeasons']:
        for season in tournament['seasons']:
            season_year = int(season['year'][-2:])
            if season_year > int(current_year[-2:]) - 2:  # Only include seasons from the last two years
                competition_name = season['name']
                tournaments_id = tournament['uniqueTournament']['id']
                season_id = season['id']
                tournaments.append([competition_name, tournaments_id, season_id])

    # Convert the list of tournaments to a pandas DataFrame
    tournaments_df = pd.DataFrame(tournaments, columns=['competition_name', 'tournaments_id', 'season_id'])
    tournaments_df['player_id'] = player_id
    
    return tournaments_df


def get_heatmap(player_id, league_id, season_id):
    """
    Fetches heatmap data for a player from a specific league and season from the Sofascore API.

    Args:
        player_id (int): Player's unique identifier in Sofascore.
        league_id (int): League's unique identifier in Sofascore.
        season_id (int): Season's unique identifier in Sofascore.

    Returns:
        DataFrame: Contains heatmap data with coordinates (x, y) and count of actions.
    """
    
    heatmap = []
    api_url = f'https://www.sofascore.com/api/v1/player/{player_id}/unique-tournament/{league_id}/season/{season_id}/heatmap/overall'
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()

        if 'points' in data:
            for point in data['points']:
                x = point.get('x', 0)
                y = point.get('y', 0)
                count = point.get('count', 0)
                heatmap.append([x, y, count])
        else:
            print(f"No heatmap data found for player {player_id} in league {league_id} and season {season_id}.")

    except:
        # Return an empty DataFrame with appropriate columns if an exception occurs
        return pd.DataFrame(columns=['x', 'y', 'count', 'player_id', 'league_id', 'season_id'])

    heatmap_df = pd.DataFrame(heatmap, columns=['x', 'y', 'count'])
    heatmap_df['player_id'] = player_id
    heatmap_df['league_id'] = league_id
    heatmap_df['season_id'] = season_id
    
    return heatmap_df