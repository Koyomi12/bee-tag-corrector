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


def show_settings():
    is_expanded = st.session_state["directory"] is None
    with st.expander("Settings", expanded=is_expanded):
        with st.form("directory_form", border=False):
            st.text_input("Directory", key="directory")
            st.form_submit_button(
                "Load",
                on_click=load_directory,
            )
        st.radio(
            "-",
            options=option_map.keys(),
            format_func=lambda option: option_map[option].capitalize(),
            on_change=switch_selection,
            horizontal=True,
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


def show_video_grid():
    grid = [st.columns(cols, border=True) for _ in range(rows)]
    for i, current_day_dance_id in enumerate(st.session_state["current_day_dance_ids"]):
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
                on_change=toggle_checkbox,
                kwargs=dict(day_dance_id=current_day_dance_id),
                value=st.session_state["checkboxes"][current_day_dance_id]
                if current_day_dance_id in st.session_state["checkboxes"]
                else False,
            )


def toggle_checkbox(day_dance_id):
    st.session_state["checkboxes"][day_dance_id] = (
        not st.session_state["checkboxes"][day_dance_id]
        if day_dance_id in st.session_state["checkboxes"]
        else True
    )


def show_forward_back():
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
    st.button(
        "back",
        on_click=set_prev_dances,
        disabled=st.session_state["current_video_idx"] <= rows * cols,
    )
    st.button(
        "forward",
        on_click=set_next_dances,
        disabled=st.session_state["current_video_idx"] >= rows_in_category.shape[0],
    )


def switch_selection():
    st.session_state["current_video_idx"] = 0
    st.session_state["selection"] = (
        TAGGED if st.session_state["selection"] == UNTAGGED else UNTAGGED
    )
    if st.session_state["directory"] is not None:
        set_first_dances()


def save():
    wrong_category_ids = get_checked_day_dance_ids()
    save_data(wrong_category_ids)
    st.session_state["checkboxes"] = {}
    set_first_dances()


def get_checked_day_dance_ids():
    return [k for k, v in st.session_state["checkboxes"].items() if v]


def save_data(wrong_category_ids):
    if len(wrong_category_ids) == 0:
        return
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


def set_first_dances():
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
    dances = rows_in_category.iloc[0 : rows * cols]
    st.session_state["current_day_dance_ids"] = dances["day_dance_id"]
    st.session_state["current_video_idx"] = dances.shape[0]


def set_next_dances():
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
    dances = rows_in_category.iloc[
        st.session_state["current_video_idx"] : st.session_state["current_video_idx"]
        + rows * cols
    ]
    st.session_state["current_day_dance_ids"] = dances["day_dance_id"]
    st.session_state["current_video_idx"] += dances.shape[0]


def set_prev_dances():
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
    start = (
        st.session_state["current_video_idx"]
        - len(st.session_state["current_day_dance_ids"])
        - rows * cols
    )
    if start < 0:
        start = 0
    dances = rows_in_category.iloc[start : start + rows * cols]
    st.session_state["current_day_dance_ids"] = dances["day_dance_id"]
    st.session_state["current_video_idx"] -= dances.shape[0]
    if st.session_state["current_video_idx"] < rows * cols:
        st.session_state["current_video_idx"] = rows * cols


if __name__ == "__main__":
    cols = 5
    rows = 2
    st.set_page_config(page_title="Bee Tag Corrector", layout="wide")
    option_map = {0: TAGGED, 1: UNTAGGED}
    if "selection" not in st.session_state:
        st.session_state["selection"] = option_map[0]
    if "current_video_idx" not in st.session_state:
        st.session_state["current_video_idx"] = 0
    if "current_day_dance_ids" not in st.session_state:
        st.session_state["current_day_dance_ids"] = []
    if "videos" not in st.session_state:
        st.session_state["videos"] = []
    if "checkboxes" not in st.session_state:
        st.session_state["checkboxes"] = {}
    if "directory" not in st.session_state:
        st.session_state["directory"] = None
    if (
        st.session_state["directory"] is not None
        and len(st.session_state["current_day_dance_ids"]) == 0
    ):
        # app start
        show_settings()
        set_first_dances()
        show_video_grid()
        show_forward_back()
    elif st.session_state["directory"] is None:
        show_settings()
    else:
        show_settings()
        show_video_grid()
        show_forward_back()
        st.button("save", on_click=save)
