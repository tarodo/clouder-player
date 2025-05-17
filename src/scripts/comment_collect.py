from dataclasses import dataclass
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from src.spotycli.config import settings

class Comment(BaseModel):
    platform: str = Field(description="Platform where the comment was found")
    text: str = Field(description="Comment text")
    author: str = Field(description="Comment author")
    date: str = Field(description="Comment date")

class Rating(BaseModel):
    platform: str = Field(description="Platform where the rating was found")
    type: str = Field(description="Type of rating (like, approval, etc.)")
    count: int = Field(description="Number of ratings")
    average: float = Field(description="Average rating if applicable")

class TrackAnalysis(BaseModel):
    comments: List[Comment] = Field(description="List of comments about the track")
    ratings: List[Rating] = Field(description="List of ratings for the track")

@dataclass
class TrackInfo:
    name: str
    artists: List[str]
    label: str

def collect_track_comments(track: TrackInfo) -> Dict[str, Any]:
    print(f"Collecting comments for {track.name} by {track.artists}")
    
    parser = PydanticOutputParser(pydantic_object=TrackAnalysis)
    
    system_prompt = """
    You're a music analysis expert. Search for comments and ratings across various platforms.
    You must respond in valid JSON format according to the schema.
    """

    prompt = PromptTemplate(
        template="""
        Find comments and ratings for:
            - Artist(s): {artists}
            - Title: {name}
            - Label: {label}

        Search across platforms like:
        - YouTube
        - Spotify
        - SoundCloud
        - Reddit
        - Music blogs
        - Social media

        {format_instructions}

        Rules:
        - Return up to 20 most relevant comments
        - Include all available ratings
        - Focus on recent and meaningful comments
        - Verify information from official sources when possible
        """,
        input_variables=["artists", "name", "label"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    llm = ChatOpenAI(
        model="sonar-pro",
        temperature=0,
        api_key=settings.perplexity_api_key,
        base_url="https://api.perplexity.ai",
    )

    chain = prompt | llm | parser

    result = chain.invoke({
        "artists": ', '.join(track.artists),
        "name": track.name,
        "label": track.label
    })

    return result.model_dump()

if __name__ == "__main__":
    # Example usage
    track = TrackInfo(
        name="Even If",
        artists=["Calibre"],
        label="Signature"
    )
    
    analysis = collect_track_comments(track)
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
