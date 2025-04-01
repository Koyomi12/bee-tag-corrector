import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

TAGGED_DANCE_DIR = "tagged-dances"
UNTAGGED_DANCE_DIR = "untagged-dances"
DATA_FILE = "data.csv"
TAGGED = "tagged"
UNTAGGED = "untagged"


def show_top():
    is_expanded = st.session_state["directory"] is None
    with st.expander("Settings", expanded=is_expanded):
        with st.form("directory_form", border=False):
            st.text_input("Directory", key="directory")
            st.form_submit_button("Load", on_click=load_stuff)
        st.segmented_control(
            "-",
            options=option_map.keys(),
            format_func=lambda option: option_map[option].capitalize(),
            selection_mode="single",
            default=0,
            on_change=switch_selection,
        )


def load_directory():
    st.session_state["current_video_idx"] = 0
    directory = Path(st.session_state["directory"])
    data_path = directory / "data.csv"
    if not data_path.exists():
        st.text(f"Could not find {DATA_FILE}")
        return
    files = list(directory.glob("*"))
    filenames = [file.name for file in files]
    if TAGGED_DANCE_DIR not in filenames and UNTAGGED_DANCE_DIR not in filenames:
        st.text(
            f"Could not find {TAGGED_DANCE_DIR} and/or {UNTAGGED_DANCE_DIR} directory"
        )
        return
    tagged_dir = directory / TAGGED_DANCE_DIR
    untagged_dir = directory / UNTAGGED_DANCE_DIR
    tagged_videos = sorted(tagged_dir.glob("*.mp4"))
    untagged_videos = sorted(untagged_dir.glob("*.mp4"))
    st.session_state["videos"] = tagged_videos + untagged_videos


def load_videos():
    data_path = Path(st.session_state["directory"]) / "data.csv"
    df = pd.read_csv(
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
    rows_in_category = df.loc[
        (df["category_label"] == st.session_state["selection"])
        & (df["corrected_category_label"].isnull())
        | (df["corrected_category_label"] == st.session_state["selection"])
    ]
    if st.session_state["current_video_idx"] >= rows_in_category.shape[0]:
        st.write("nothing left")
        return
    with st.form("checkbox_form"):
        grid = [st.columns(cols, border=True) for _ in range(rows)]
        st.session_state["current_chunk"] = []
        for i in range(rows * cols):
            if st.session_state["current_video_idx"] >= rows_in_category.shape[0]:
                break
            current_day_dance_id = rows_in_category.iat[
                st.session_state["current_video_idx"], 0
            ]
            current_video = next(
                (
                    vid
                    for vid in st.session_state["videos"]
                    if vid.stem == current_day_dance_id
                ),
                None,
            )
            if current_video is None:
                st.write("No matching video file found")
                break
            row = int(math.floor(i / cols))
            col = i % cols
            with grid[row][col]:
                st.write(current_day_dance_id)
                # Hide control bar on videos
                st.html("""
                <style>
                video::-webkit-media-controls {
                    display: none !important;
                }
                video::-webkit-media-controls-panel {
                    display: none !important;
                }
                video::-webkit-media-controls-play-button {
                    display: none !important;
                }
                </style>
                """)
                st.video(
                    current_video,
                    loop=True,
                    autoplay=True,
                )
                st.checkbox(
                    "Wrong Category",
                    key=current_day_dance_id,
                )
            st.session_state["current_video_idx"] += 1
            st.session_state["current_chunk"].append(current_day_dance_id)
        st.form_submit_button("Save", on_click=save_and_load_next)


def load_stuff():
    show_top()
    if st.session_state["directory"] is not None:
        load_directory()
        load_videos()


def switch_selection():
    st.session_state["current_video_idx"] = 0
    st.session_state["selection"] = (
        TAGGED if st.session_state["selection"] == UNTAGGED else UNTAGGED
    )
    show_top()
    load_videos()


def get_checked_day_dance_ids():
    return [id for id in st.session_state["current_chunk"] if st.session_state[id]]


def save_data(wrong_category_ids):
    data_path = Path(st.session_state["directory"]) / "data.csv"
    df = pd.read_csv(
        data_path,
        index_col="day_dance_id",
        dtype={
            "day_dance_id": "string",
            "waggle_id": "string",
            "category": "Int64",
            "category_label": "string",
            "corrected_category": "Int64",
            "corrected_category_label": "string",
        },
    )
    for id in wrong_category_ids:
        corrected_category = df.at[id, "corrected_category"]
        if pd.isna(corrected_category):
            category = df.at[id, "category"]
            df.at[id, "corrected_category"] = 0 if category == 1 else 1
            category_label = df.at[id, "category_label"]
            df.at[id, "corrected_category_label"] = (
                "tagged" if category_label == "untagged" else "untagged"
            )
        else:
            df.at[id, "corrected_category"] = np.nan
            df.at[id, "corrected_category_label"] = ""
    df.to_csv(data_path)


def save_and_load_next():
    checked_ids = get_checked_day_dance_ids()
    st.session_state["current_video_idx"] -= len(checked_ids)
    save_data(checked_ids)
    show_top()
    load_videos()


if __name__ == "__main__":
    cols = 5
    rows = 2
    st.set_page_config(page_title="Bee Tag Corrector", layout="wide")
    option_map = {0: TAGGED, 1: UNTAGGED}
    if "selection" not in st.session_state:
        st.session_state["selection"] = option_map[0]
    if "current_video_idx" not in st.session_state:
        st.session_state["current_video_idx"] = 0
    if "current_day_dance_id" not in st.session_state:
        st.session_state["current_day_dance_id"] = ""
    if "videos" not in st.session_state:
        st.session_state["videos"] = []
    if "current_chunk" not in st.session_state:
        st.session_state["current_chunk"] = []
    if "directory" not in st.session_state:
        st.session_state["directory"] = None
        # start app
        show_top()
