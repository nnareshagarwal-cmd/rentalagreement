"""
Google Places API (New) & Legacy Places Service.
Provides automated society/apartment search, postal address resolution,
PIN code extraction, and autocomplete predictions for AgreementAI.
"""

import os
import time
import logging
import re
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger("AgreementAI_Places")

# In-memory TTL cache to minimize billable Google Maps API calls
_PLACES_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 3600 * 24  # 24 hours


from config import Config

class PlacesService:
    """Service to interact with Google Places API (New) and Geocoding APIs."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else getattr(Config, "GOOGLE_MAPS_API_KEY", os.getenv("GOOGLE_MAPS_API_KEY", ""))

    def is_configured(self) -> bool:
        """Returns True if a Google Maps API Key is configured."""
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def search_and_resolve(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a property / society / apartment name in India and resolve
        its official postal address, city, state, and PIN code.
        """
        if not self.is_configured() or not query or len(query.strip()) < 3:
            return None

        clean_query = query.strip()
        cache_key = f"resolve_{clean_query.lower()}"
        cached = _PLACES_CACHE.get(cache_key)
        if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL_SECONDS:
            return cached.get("data")

        # 1. Try Google Places API (New) Text Search
        result = self._search_places_new(clean_query)

        # 2. Fallback to Legacy Text Search if needed
        if not result:
            result = self._search_places_legacy(clean_query)

        if result:
            _PLACES_CACHE[cache_key] = {
                "data": result,
                "_ts": time.time(),
            }
            logger.info(f"Google Places resolved '{clean_query}' -> {result.get('formatted_address')}")

        return result

    def autocomplete(self, query: str) -> List[Dict[str, Any]]:
        """
        Returns top 5 autocomplete predictions for Indian addresses / societies.
        """
        if not self.is_configured() or not query or len(query.strip()) < 2:
            return []

        clean_query = query.strip()
        cache_key = f"ac_{clean_query.lower()}"
        cached = _PLACES_CACHE.get(cache_key)
        if cached and (time.time() - cached.get("_ts", 0)) < 3600:
            return cached.get("data", [])

        # 1. Try Places API (New) Autocomplete
        suggestions = self._autocomplete_new(clean_query)

        # 2. Fallback to legacy Autocomplete
        if not suggestions:
            suggestions = self._autocomplete_legacy(clean_query)

        if suggestions:
            _PLACES_CACHE[cache_key] = {
                "data": suggestions,
                "_ts": time.time(),
            }

        return suggestions

    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Fetch structured address details given a place_id."""
        if not self.is_configured() or not place_id:
            return None

        cache_key = f"details_{place_id}"
        cached = _PLACES_CACHE.get(cache_key)
        if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL_SECONDS:
            return cached.get("data")

        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "place_id,name,formatted_address,address_components,geometry",
            "key": self.api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=6)
            if resp.ok:
                data = resp.json()
                if data.get("status") == "OK" and "result" in data:
                    parsed = self._parse_legacy_place_result(data["result"])
                    if parsed:
                        _PLACES_CACHE[cache_key] = {"data": parsed, "_ts": time.time()}
                        return parsed
        except Exception as e:
            logger.warning(f"Google Place Details error: {e}")

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Handlers: Google Places API (New)
    # ─────────────────────────────────────────────────────────────────────────

    def _search_places_new(self, query: str) -> Optional[Dict[str, Any]]:
        """Queries https://places.googleapis.com/v1/places:searchText"""
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.addressComponents,places.location"
            ),
        }
        payload = {
            "textQuery": query,
            "regionCode": "IN",
            "languageCode": "en",
            "maxResultCount": 1,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=6)
            if resp.ok:
                data = resp.json()
                places = data.get("places", [])
                if places:
                    place = places[0]
                    return self._parse_new_place_result(place, query=query)
        except Exception as e:
            logger.warning(f"Places API (New) searchText error: {e}")

        return None

    def _parse_new_place_result(self, place: Dict[str, Any], query: str = "") -> Dict[str, Any]:
        """Parses a Place object from Google Places API (New)."""
        display_name = (place.get("displayName", {}) or {}).get("text", "")
        formatted_address = place.get("formattedAddress", "")
        place_id = place.get("id", "")
        location = place.get("location", {})

        components = place.get("addressComponents", [])
        extracted = self._extract_address_components_new(components)

        society = display_name or extracted.get("premise", "")
        if not society or "road" in society.lower() or "colony" in society.lower():
            if query:
                candidate_soc = query.split(",")[0].strip().title()
                if len(candidate_soc) > 3 and not re.search(r'\b(rent|deposit|owner|tenant|flat|apartment)\b', candidate_soc, re.I):
                    society = candidate_soc
        
        # Ensure society name is at the start of full postal address
        if society and society.lower() not in formatted_address.lower():
            full_addr = f"{society}, {formatted_address}"
        else:
            full_addr = formatted_address or society

        return {
            "place_id": place_id,
            "society_name": society,
            "property_address": full_addr,
            "locality": extracted.get("sublocality") or extracted.get("locality", ""),
            "city": extracted.get("city", ""),
            "state": extracted.get("state", ""),
            "state_code": extracted.get("state_code", ""),
            "pincode": extracted.get("pincode", ""),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "source": "google_places",
        }

    def _extract_address_components_new(self, components: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extracts city, state, pin code from Places (New) address components."""
        info = {
            "premise": "",
            "route": "",
            "sublocality": "",
            "locality": "",
            "city": "",
            "state": "",
            "state_code": "",
            "pincode": "",
        }
        for comp in components:
            types = comp.get("types", [])
            long_text = comp.get("longText", "")
            short_text = comp.get("shortText", "")

            if "premise" in types or "subpremise" in types or "point_of_interest" in types:
                if not info["premise"]:
                    info["premise"] = long_text
            elif "route" in types or "street_address" in types:
                info["route"] = long_text
            elif "sublocality_level_1" in types or "sublocality" in types:
                info["sublocality"] = long_text
            elif "locality" in types:
                info["locality"] = long_text
                if not info["city"]:
                    info["city"] = long_text
            elif "administrative_area_level_2" in types and not info["city"]:
                info["city"] = long_text
            elif "administrative_area_level_1" in types:
                info["state"] = long_text
                info["state_code"] = short_text
            elif "postal_code" in types:
                info["pincode"] = long_text

        return info

    def _autocomplete_new(self, query: str) -> List[Dict[str, Any]]:
        """Queries Places API (New) Autocomplete."""
        url = "https://places.googleapis.com/v1/places:autocomplete"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }
        payload = {
            "input": query,
            "includedRegionCodes": ["IN"],
            "languageCode": "en",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=5)
            if resp.ok:
                data = resp.json()
                suggestions = []
                for s in data.get("suggestions", [])[:5]:
                    place_pred = s.get("placePrediction", {})
                    place_id = place_pred.get("placeId", "")
                    main_text = (place_pred.get("structuredFormat", {}).get("mainText", {}) or {}).get("text", "")
                    secondary_text = (place_pred.get("structuredFormat", {}).get("secondaryText", {}) or {}).get("text", "")
                    full_text = (place_pred.get("text", {}) or {}).get("text", "")

                    if place_id:
                        suggestions.append({
                            "place_id": place_id,
                            "title": main_text or full_text,
                            "subtitle": secondary_text,
                            "description": full_text or f"{main_text}, {secondary_text}",
                        })
                return suggestions
        except Exception as e:
            logger.warning(f"Places API (New) Autocomplete error: {e}")

        return []

    # ─────────────────────────────────────────────────────────────────────────
    # Internal Handlers: Legacy Places API
    # ─────────────────────────────────────────────────────────────────────────

    def _search_places_legacy(self, query: str) -> Optional[Dict[str, Any]]:
        """Queries legacy maps textsearch endpoint."""
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "region": "in",
            "key": self.api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=6)
            if resp.ok:
                data = resp.json()
                if data.get("status") == "OK" and data.get("results"):
                    first = data["results"][0]
                    # If place details needed for components:
                    place_id = first.get("place_id")
                    if place_id:
                        return self.get_place_details(place_id)
                    return self._parse_legacy_place_result(first)
        except Exception as e:
            logger.warning(f"Legacy Places search error: {e}")

        return None

    def _autocomplete_legacy(self, query: str) -> List[Dict[str, Any]]:
        """Queries legacy places autocomplete endpoint."""
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": query,
            "components": "country:in",
            "key": self.api_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=5)
            if resp.ok:
                data = resp.json()
                if data.get("status") == "OK":
                    results = []
                    for pred in data.get("predictions", [])[:5]:
                        results.append({
                            "place_id": pred.get("place_id"),
                            "title": pred.get("structured_formatting", {}).get("main_text", pred.get("description")),
                            "subtitle": pred.get("structured_formatting", {}).get("secondary_text", ""),
                            "description": pred.get("description"),
                        })
                    return results
        except Exception as e:
            logger.warning(f"Legacy Autocomplete error: {e}")

        return []

    def _parse_legacy_place_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parses a Place Details result from legacy API."""
        name = result.get("name", "")
        formatted_address = result.get("formatted_address", "")
        place_id = result.get("place_id", "")
        geometry = result.get("geometry", {})
        location = geometry.get("location", {})

        components = result.get("address_components", [])
        info = {
            "sublocality": "",
            "locality": "",
            "city": "",
            "state": "",
            "state_code": "",
            "pincode": "",
        }
        for comp in components:
            types = comp.get("types", [])
            long_name = comp.get("long_name", "")
            short_name = comp.get("short_name", "")

            if "sublocality_level_1" in types or "sublocality" in types:
                info["sublocality"] = long_name
            elif "locality" in types:
                info["locality"] = long_name
                if not info["city"]:
                    info["city"] = long_name
            elif "administrative_area_level_2" in types and not info["city"]:
                info["city"] = long_name
            elif "administrative_area_level_1" in types:
                info["state"] = long_name
                info["state_code"] = short_name
            elif "postal_code" in types:
                info["pincode"] = long_name

        society = name or info.get("sublocality") or ""
        if society and society.lower() not in formatted_address.lower():
            full_addr = f"{society}, {formatted_address}"
        else:
            full_addr = formatted_address or society

        return {
            "place_id": place_id,
            "society_name": society,
            "property_address": full_addr,
            "locality": info["sublocality"] or info["locality"],
            "city": info["city"],
            "state": info["state"],
            "state_code": info["state_code"],
            "pincode": info["pincode"],
            "latitude": location.get("lat"),
            "longitude": location.get("lng"),
            "source": "google_places",
        }


# Global singleton instance
places_service = PlacesService()
