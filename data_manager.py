"""Data persistence manager for the Variety Friday bot."""
import json
import logging
from pathlib import Path
from typing import Set, Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class DataManager:
    """Handles data persistence for bot state."""
    
    def __init__(self, data_file: str = "bot_data.json"):
        self.data_file = Path(data_file)
        self._data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load data from JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded data from {self.data_file}")
                    return data
            except Exception as e:
                logger.error(f"Error loading data from {self.data_file}: {e}")
        
        # Return default structure
        return {
            "games": [],
            "vote_message_id": None,
            "last_event_id": None,
            "reminder_message_id": None,
            "yes_participants": [],
            "no_participants": []
        }
    
    def save_data(self) -> bool:
        """Save data to JSON file."""
        try:
            # Convert sets to lists for JSON serialization
            data_to_save = self._data.copy()
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            logger.info(f"Data saved to {self.data_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving data to {self.data_file}: {e}")
            return False
    
    # Games management
    @property
    def games(self) -> List[str]:
        return self._data.get("games", [])
    
    def add_game(self, game_name: str) -> bool:
        """Add a game to the list."""
        if game_name.lower() not in [g.lower() for g in self.games]:
            self._data["games"].append(game_name)
            self.save_data()
            return True
        return False
    
    def remove_game(self, game_name: str) -> bool:
        """Remove a game from the list."""
        for game in self.games:
            if game.lower() == game_name.lower():
                self._data["games"].remove(game)
                self.save_data()
                return True
        return False
    
    def clear_games(self):
        """Clear all games."""
        self._data["games"] = []
        self.save_data()
    
    # Message IDs
    @property
    def vote_message_id(self) -> Optional[int]:
        return self._data.get("vote_message_id")
    
    @vote_message_id.setter
    def vote_message_id(self, value: Optional[int]):
        self._data["vote_message_id"] = value
        self.save_data()
    
    @property
    def last_event_id(self) -> Optional[int]:
        return self._data.get("last_event_id")
    
    @last_event_id.setter
    def last_event_id(self, value: Optional[int]):
        self._data["last_event_id"] = value
        self.save_data()
    
    @property
    def reminder_message_id(self) -> Optional[int]:
        return self._data.get("reminder_message_id")
    
    @reminder_message_id.setter
    def reminder_message_id(self, value: Optional[int]):
        self._data["reminder_message_id"] = value
        self.save_data()
    
    # Participants management
    @property
    def yes_participants(self) -> Set[int]:
        return set(self._data.get("yes_participants", []))
    
    @property
    def no_participants(self) -> Set[int]:
        return set(self._data.get("no_participants", []))
    
    def add_yes_participant(self, user_id: int):
        """Add a user to yes participants."""
        yes_set = set(self._data.get("yes_participants", []))
        no_set = set(self._data.get("no_participants", []))
        
        yes_set.add(user_id)
        no_set.discard(user_id)
        
        self._data["yes_participants"] = list(yes_set)
        self._data["no_participants"] = list(no_set)
        self.save_data()
    
    def add_no_participant(self, user_id: int):
        """Add a user to no participants."""
        yes_set = set(self._data.get("yes_participants", []))
        no_set = set(self._data.get("no_participants", []))
        
        no_set.add(user_id)
        yes_set.discard(user_id)
        
        self._data["yes_participants"] = list(yes_set)
        self._data["no_participants"] = list(no_set)
        self.save_data()
    
    def remove_yes_participant(self, user_id: int):
        """Remove a user from yes participants."""
        yes_set = set(self._data.get("yes_participants", []))
        yes_set.discard(user_id)
        self._data["yes_participants"] = list(yes_set)
        self.save_data()
    
    def remove_no_participant(self, user_id: int):
        """Remove a user from no participants."""
        no_set = set(self._data.get("no_participants", []))
        no_set.discard(user_id)
        self._data["no_participants"] = list(no_set)
        self.save_data()
    
    def clear_participants(self):
        """Clear all participants."""
        self._data["yes_participants"] = []
        self._data["no_participants"] = []
        self.save_data()
