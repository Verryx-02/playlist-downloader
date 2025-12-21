# A comparative benchmark must be created to approximately measure whether matching algorithm A is better than algorithm B.

## Input:
`A_input.tsv` and `B_input.tsv`

### FileA:
Each row can be only one of the following options:

```bash
spotify_id \t A_youtube_url
spotify_id
```

### FileB:
Each row can be only one of the following options:

```bash
spotify_id \t B_youtube_url
spotify_id
```

Where:
`spotify_id` is the unique ID of the song on Spotify (see the file `spot_downloader/spotify/models.py`).

## Output:
`Output.tsv`, where each row can be only one of the following options:

```bash
spotify_id \t A_youtube_url \t B_youtube_url
spotify_id \t A_youtube_url
spotify_id \t B_youtube_url
spotify_id
```

With:
`A_youtube_url != B_youtube_url`

NOTE: There are NO spaces in the files. I added them only to make the structure clearer. In reality, it would look like this, for example:
`spotify_id\tA_youtube_url\tB_youtube_url`

## Benchmark behavior:
The benchmark reads the IDs from file A and looks for the same ID in file B.

- If **both** `A_youtube_url` and `B_youtube_url` are missing, append only `spotify_id` to `Output.tsv`
- If `A_youtube_url` for the same ID `==` `B_youtube_url`, do nothing and move on to the next `spotify_id`
- If `A_youtube_url` for the same ID `!=` `B_youtube_url`, append `spotify_id \t A_youtube_url \t B_youtube_url` to `Output.tsv`
- If `A_youtube_url` is missing, append `spotify_id \t B_youtube_url` to `Output.tsv`
- If `B_youtube_url` is missing, append `spotify_id \t A_youtube_url` to `Output.tsv`
