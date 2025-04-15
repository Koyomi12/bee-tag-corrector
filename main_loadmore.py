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
            st.form_submit_button("Load", on_click=load_directory)
        st.radio(
            "Category to Label",
            options=option_map.keys(),
            format_func=lambda option: option_map[option].capitalize(),
            key="category_selection",
            on_change=reload_videos,
            horizontal=True,
        )


def load_directory():
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

    # Save video file paths (day_dance_id -> video file Path) into session state
    st.session_state["videos"] = {
        v.stem: v
        for v in list(tagged_dir.glob("*.mp4")) + list(untagged_dir.glob("*.mp4"))
    }

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

    # Reset pagination state and checkmarked_ids
    st.session_state["current_page"] = 1
    st.session_state["checkmarked_ids"].clear()
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

    # Reset the pagination and checkmarked_ids whenever the category changes.
    st.session_state["current_page"] = 1
    st.session_state["checkmarked_ids"].clear()


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
            cols_container = st.columns(cols, border=True)
            for c in range(cols):
                idx = r * cols + c
                if idx >= page_total:
                    break
                # Get the day_dance_id (assumed to be the first column)
                day_dance_id = page_df.iat[idx, 0]
                with cols_container[c]:
                    # "corrected_category_label" is assumed to be the seventh column
                    if pd.isna(page_df.iat[idx, 6]):
                        st.write(day_dance_id)
                    else:
                        st.write(f"{day_dance_id} - corrected")
                    vid_path = st.session_state.get("videos", {}).get(day_dance_id)
                    if vid_path:
                        st.video(str(vid_path), loop=True, autoplay=True)
                    else:
                        st.write("No video found")
                    st.checkbox(
                        "Wrong Category",
                        key=day_dance_id,
                        value=day_dance_id
                        in st.session_state.get("checkmarked_ids", set()),
                    )

        # Column ratio is a guess and differs based on screen size and
        # resolution. Streamlit doesn't have a good solution.
        col1, col2, _ = st.columns([1, 1, 8])
        with col1:
            st.form_submit_button(
                "Save/Load Previous",
                disabled=current_page == 1,
                on_click=partial(on_save, current_page, "previous"),
            )
        with col2:
            st.form_submit_button(
                "Save/Load Next" if current_page < total_pages else "Save",
                on_click=partial(on_save, current_page, "next"),
            )


def on_save(page, mode):
    """
    Saves corrections for the given page. Increments or decrements current_page
    session_state based on mode.
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

    current_day_dance_ids = page_df["day_dance_id"].tolist()
    # Collect day_dance_ids for which "Wrong Category" is checkmarked.
    checkmarked_ids = set()
    for d_id in current_day_dance_ids:
        if st.session_state.get(d_id, False):
            checkmarked_ids.add(d_id)
            # Store day_dance_ids for which "Wrong Category" is checkmarked in
            # separate session state, because the checkbox element keys are
            # only stored in session state as long as they are being rendered
            # and discarded when the next page is loaded.
            st.session_state["checkmarked_ids"].add(d_id)

    uncheckmarked_ids = (
        st.session_state["checkmarked_ids"]
        .difference(checkmarked_ids)
        .intersection(current_day_dance_ids)
    )

    # Forget day_dance_ids for which "Wrong Category" was not checkmarked.
    for id in uncheckmarked_ids:
        st.session_state["checkmarked_ids"].discard(id)

    # Update the CSV (stored in session_state["data_df"]) with corrections.
    df = st.session_state["data_df"]
    swap_category_ids = checkmarked_ids.union(uncheckmarked_ids)
    for d_id in swap_category_ids:
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
            df.loc[df["day_dance_id"] == d_id, "corrected_category_label"] = np.nan
    st.session_state["data_df"] = df

    # Save the CSV back to disk.
    directory = Path(st.session_state["directory"])
    data_path = directory / DATA_FILE
    df.to_csv(data_path, index=False)
    st.success(f"Saved corrections for page {page}.")

    # If more pages exist, increment or decrement current_page.
    if page < total_pages and mode == "next":
        st.session_state["current_page"] = current_page + 1
    elif page > 1 and mode == "previous":
        st.session_state["current_page"] = current_page - 1


def main():
    st.set_page_config(page_title="Bee Tag Corrector", layout="wide")

    # Initialize session state variables if they don't exist
    if "directory" not in st.session_state:
        st.session_state["directory"] = None
    if "data_df" not in st.session_state:
        st.session_state["data_df"] = None
    if "rows_to_show" not in st.session_state:
        st.session_state["rows_to_show"] = pd.DataFrame()
    if "videos" not in st.session_state:
        st.session_state["videos"] = []
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = 1
    if "checkmarked_ids" not in st.session_state:
        st.session_state["checkmarked_ids"] = set()

    global option_map
    option_map = {0: TAGGED, 1: UNTAGGED}

    show_settings()
    show_videos()


if __name__ == "__main__":
    main()
