from dataclasses import dataclass

from fastapi import HTTPException

from app.services.base import TransfermarktBase
from app.utils.utils import extract_from_url
from app.utils.xpath import Competitions


@dataclass
class TransfermarktCompetitionClubs(TransfermarktBase):
    """
    A class for retrieving and parsing the list of football clubs in a specific competition on Transfermarkt.

    Args:
        competition_id (str): The unique identifier of the competition.
        season_id (str): The season identifier. If not provided, it will be extracted from the URL.
        URL (str): The URL template for a standard (league) competition page on Transfermarkt.
        URL_CUP (str): The URL template for a cup-type (group stage / knockout) competition page.
    """

    competition_id: str = None
    season_id: str = None
    URL: str = "https://www.transfermarkt.com/-/startseite/wettbewerb/{competition_id}/plus/?saison_id={season_id}"
    URL_CUP: str = "https://www.transfermarkt.com/-/startseite/pokalwettbewerb/{competition_id}/plus/?saison_id={season_id}"

    def __post_init__(self) -> None:
        """Initialize the TransfermarktCompetitionClubs class.

        Transfermarkt serves standard leagues under the ``wettbewerb`` path and cup-type
        competitions (group stage + knockout, e.g. Campeonato Brasileiro Série C, Fase Final
        do Campeonato de Portugal, play-offs) under the ``pokalwettbewerb`` path. The stock
        endpoint only knew about ``wettbewerb`` and returned a hard 404 for every cup-type
        competition. We try the league path first, then transparently fall back to the cup path.
        """
        league_url = self.URL.format(competition_id=self.competition_id, season_id=self.season_id)
        cup_url = self.URL_CUP.format(competition_id=self.competition_id, season_id=self.season_id)

        self.URL = league_url
        try:
            self.page = self.request_url_page()
            # A valid league page exposes the competition name. If it's missing, treat the
            # league path as a miss and fall through to the cup path below.
            if not self.get_text_by_xpath(Competitions.Profile.NAME):
                raise HTTPException(status_code=404, detail="empty league page")
        except HTTPException:
            self.URL = cup_url
            self.page = self.request_url_page()

        # Final guard: if neither path yielded a competition name, raise a clean 404.
        self.raise_exception_if_not_found(xpath=Competitions.Profile.NAME)

    def __parse_competition_clubs(self) -> list:
        """
        Parse the competition's page and extract information about the football clubs participating
            in the competition.

        Returns:
            list: A list of dictionaries, where each dictionary contains information about a
                football club in the competition, including the club's unique identifier and name.
        """
        urls = self.get_list_by_xpath(Competitions.Clubs.URLS)
        names = self.get_list_by_xpath(Competitions.Clubs.NAMES)
        ids = [extract_from_url(url) for url in urls]

        return [{"id": idx, "name": name} for idx, name in zip(ids, names)]

    def get_competition_clubs(self) -> dict:
        """
        Retrieve and parse the list of football clubs participating in a specific competition.

        Returns:
            dict: A dictionary containing the competition's unique identifier, name, season identifier, list of clubs
                  participating in the competition, and the timestamp of when the data was last updated.
        """
        self.response["id"] = self.competition_id
        self.response["name"] = self.get_text_by_xpath(Competitions.Profile.NAME)
        self.response["seasonId"] = extract_from_url(
            self.get_text_by_xpath(Competitions.Profile.URL),
            "season_id",
        )
        self.response["clubs"] = self.__parse_competition_clubs()

        return self.response
