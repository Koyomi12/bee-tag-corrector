import math
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# Constants for directory names and data file
TAGGED_DANCE_DIR = "tagged-dances"
UNTAGGED_DANCE_DIR = "untagged-dances"
DATA_FILE = "data.csv"
TAGGED = "tagged"
UNTAGGED = "untagged"

# How many rows of videos to show per page (each page will have PAGE_ROWS * number_of_columns videos)
PAGE_ROWS = 2


def show_settings():
    with st.expander("Settings", expanded=True):
        with st.form("directory_form", clear_on_submit=False):
            st.text_input("Directory", key="directory")
            st.number_input(
                "Number of columns",
                value=5,
                min_value=1,
                max_value=10,
                step=1,
                key="cols",
            )
            st.form_submit_button("Load", on_click=load_stuff)
        st.radio(
            "Category to Label",
            options=option_map.keys(),
            format_func=lambda option: option_map[option].capitalize(),
            key="category_selection",
            on_change=reload_videos,
            horizontal=True,
        )


def load_stuff():
    """Called when the user clicks Load after entering the directory."""
    directory = Path(st.session_state["directory"])
    data_path = directory / DATA_FILE

    if not data_path.exists():
        st.warning(f"Could not find {DATA_FILE} in {directory}")
        return

    # Check if subdirectories exist
    tagged_dir = directory / TAGGED_DANCE_DIR
    untagged_dir = directory / UNTAGGED_DANCE_DIR
    if not tagged_dir.exists() or not untagged_dir.exists():
        st.warning(
            f"Could not find {TAGGED_DANCE_DIR} or {UNTAGGED_DANCE_DIR} in {directory}"
        )
        return

    # Save video file paths (as Path objects) into session state
    st.session_state["tagged_videos"] = sorted(tagged_dir.glob("*.mp4"))
    st.session_state["untagged_videos"] = sorted(untagged_dir.glob("*.mp4"))

    # Load the CSV data into session state
    st.session_state["data_df"] = pd.read_csv(
        data_path,
        dtype={
            "day_dance_id": "string",
            "waggle_id": "string",
            "category": "Int64",
            "category_label": "string",
            "corrected_category": "Int64",
            "corrected_category_label": "string",
        },
    )

    # Reset pagination state
    st.session_state["current_page"] = 1
    reload_videos()


def reload_videos():
    """Filters the CSV data for the selected category and stores the rows to show."""
    if "data_df" not in st.session_state:
        return  # Nothing loaded yet

    selected_label = option_map[
        st.session_state["category_selection"]
    ]  # "tagged" or "untagged"
    df = st.session_state["data_df"]

    # Filter rows: show if the original label equals selection and not yet corrected,
    # or if the corrected label equals the selection.
    rows_in_category = df.loc[
        (
            (df["category_label"] == selected_label)
            & (df["corrected_category_label"].isnull())
        )
        | (df["corrected_category_label"] == selected_label)
    ]
    st.session_state["rows_to_show"] = rows_in_category

    # Reset the pagination whenever the category changes.
    st.session_state["current_page"] = 1


def show_videos():
    """Displays the videos for the current page inside a grid."""
    if "rows_to_show" not in st.session_state:
        return

    rows_to_show = st.session_state["rows_to_show"]
    if rows_to_show.empty:
        st.write("No videos found for this category.")
        return

    # Get user-specified number of columns (default is 5)
    cols = st.session_state.get("cols", 5)
    page_size = PAGE_ROWS * cols
    total_videos = rows_to_show.shape[0]
    total_pages = math.ceil(total_videos / page_size)

    st.markdown(f"**Total videos:** {total_videos} | **Pages:** {total_pages}")

    # Retrieve video lookup dictionaries (day_dance_id -> video file Path)
    tagged_lookup = {v.stem: v for v in st.session_state.get("tagged_videos", [])}
    untagged_lookup = {v.stem: v for v in st.session_state.get("untagged_videos", [])}

    current_page = st.session_state.get("current_page", 1)
    # Render videos for current_page in a grid with PAGE_ROWS rows and 'cols' columns.
    st.markdown(f"Page {current_page} of {total_pages}")
    with st.form("form_page"):
        # Calculate the subset of rows for this page
        start_idx = (current_page - 1) * page_size
        end_idx = min(current_page * page_size, total_videos)
        page_df = rows_to_show.iloc[start_idx:end_idx]
        page_total = page_df.shape[0]
        n_grid_rows = math.ceil(page_total / cols)
        for r in range(n_grid_rows):
            cols_container = st.columns(cols)
            for c in range(cols):
                idx = r * cols + c
                if idx >= page_total:
                    break
                # Get the day_dance_id (assumed to be the first column)
                day_dance_id = page_df.iat[idx, 0]
                vid_path = tagged_lookup.get(day_dance_id) or untagged_lookup.get(
                    day_dance_id
                )
                with cols_container[c]:
                    st.write(day_dance_id)
                    if vid_path:
                        st.video(str(vid_path), loop=True, autoplay=True)
                    else:
                        st.write("No video found")
                    st.checkbox("Wrong Category", key=day_dance_id)

        # Determine the button label:
        # If there are more pages, label "Save/Load Next".
        # Otherwise (for current page with no further pages, or any previous page) label "Save".
        if current_page < total_pages:
            button_label = "Save/Load Next"
        else:
            button_label = "Save"
        st.form_submit_button(button_label, on_click=partial(on_save, current_page))


def on_save(page):
    """
    Saves corrections for the given page. If additional pages remain,
    increments the current_page to load the next page.
    """
    cols = st.session_state.get("cols", 5)
    page_size = PAGE_ROWS * cols
    rows_to_show = st.session_state["rows_to_show"]
    total_videos = rows_to_show.shape[0]
    total_pages = math.ceil(total_videos / page_size)
    current_page = st.session_state.get("current_page", 1)

    # Determine the rows corresponding to this page.
    start_idx = (page - 1) * page_size
    end_idx = min(page * page_size, total_videos)
    page_df = rows_to_show.iloc[start_idx:end_idx]

    # Collect day_dance_ids for which "Wrong Category" is checked.
    checked_ids = []
    for d_id in page_df["day_dance_id"].tolist():
        if st.session_state.get(d_id, False):
            checked_ids.append(d_id)

    # Update the CSV (stored in session_state["data_df"]) with corrections.
    df = st.session_state["data_df"]
    for d_id in checked_ids:
        corrected_category = df.loc[
            df["day_dance_id"] == d_id, "corrected_category"
        ].values[0]
        if pd.isna(corrected_category):
            category = df.loc[df["day_dance_id"] == d_id, "category"].values[0]
            current_label = df.loc[df["day_dance_id"] == d_id, "category_label"].values[
                0
            ]
            new_cat = 0 if category == 1 else 1
            df.loc[df["day_dance_id"] == d_id, "corrected_category"] = new_cat
            df.loc[df["day_dance_id"] == d_id, "corrected_category_label"] = (
                TAGGED if current_label == UNTAGGED else UNTAGGED
            )
        else:
            df.loc[df["day_dance_id"] == d_id, "corrected_category"] = np.nan
            df.loc[df["day_dance_id"] == d_id, "corrected_category_label"] = ""
    st.session_state["data_df"] = df

    # Save the CSV back to disk.
    directory = Path(st.session_state["directory"])
    data_path = directory / DATA_FILE
    df.to_csv(data_path, index=False)
    st.success(f"Saved corrections for page {page}.")

    # If more pages exist, increment current_page.
    if page < total_pages:
        st.session_state["current_page"] = current_page + 1


def main():
    st.set_page_config(page_title="Bee Tag Corrector", layout="wide")

    # Initialize session state variables if they don't exist
    if "directory" not in st.session_state:
        st.session_state["directory"] = None
    if "data_df" not in st.session_state:
        st.session_state["data_df"] = None
    if "rows_to_show" not in st.session_state:
        st.session_state["rows_to_show"] = pd.DataFrame()
    if "tagged_videos" not in st.session_state:
        st.session_state["tagged_videos"] = []
    if "untagged_videos" not in st.session_state:
        st.session_state["untagged_videos"] = []
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = 1

    global option_map
    option_map = {0: TAGGED, 1: UNTAGGED}

    show_settings()
    show_videos()


if __name__ == "__main__":
    main()
