from extractor_service import extract_card_data

class CardController:
    @staticmethod
    def process_card(image_path: str):
        return extract_card_data(image_path)
