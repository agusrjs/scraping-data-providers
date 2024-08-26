# Scraping Data Providers

This project involves scraping data from various football data providers (Sofascore, Fotmob, and Fbref) to obtain information on teams and players from a specific season of the required competition. By selecting the most relevant data from each source, we gather insights on player positioning, shots, and other characteristics.

## Data Sources and Features
The following outlines the main features provided by each data source, highlighting their distinctive offerings.

### Sofascore
- **Player Heatmaps:** Provides heatmaps for players throughout the season, capturing spatial data not offered by all providers.
- **Lineups by Match:** Offers tentative lineups before matches, which are then updated during the game to reflect the actual lineups. This feature is particularly strong with Sofascore.
- **Average Positions:** Almost exclusively available from this provider, offering average positional data beyond what's available in paid services.
- **Attack Map:** Divides the pitch into six sections and assigns an attack value to indicate which areas of the pitch see the most attacks from each team. (Next to)

### Fotmob
- **Shots Map:** Includes detailed shot maps for players during the season, incorporating expected goals (xG) values.
- **Player Positions:** Records and prioritizes the positions a player occupies, based on frequency of use, providing valuable insights into player positioning.
- **Injuries and Suspensions:** Provides a list of players unavailable for each match due to injuries or suspensions. (Next to)

### Fbref
- **Teams Stats:** Known for delivering extensive advanced statistics, allowing for deep comparisons between teams in a league.
- **Players Stats:** Provides comparative statistics for players based on their position, assigning percentiles among players with similar roles and competitive levels.

## Setup

1. **Install Dependencies:** Ensure that you have the required libraries installed. Use the following command to install them:
    ```bash
    pip install -r requirements.txt
    ```

2. **Run the Scripts:** Each provider has its own script. Execute the scripts to scrape the data and generate CSV files in the `data` folder:
    - **Sofascore:** Scrapes player heatmaps, lineups, average positions, and attack maps.
    - **Fotmob:** Scrapes shot maps, player positions, and upcoming injuries and suspensions.
    - **Fbref:** Scrapes team and player stats.

3. **Review Data:** The data will be saved in CSV files within the `data` folder, with filenames prefixed by the respective provider name.

## Files

- `pvd_Sofascore.py`: Contains functions to scrape data from Sofascore.
- `pvd_Fotmob.py`: Contains functions to scrape data from Fotmob.
- `pvd_Fbref.py`: Contains functions to scrape data from Fbref.

---

This README provides an overview of your project and instructions for setup and use. Feel free to make any additional adjustments or updates!