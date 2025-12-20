# Bisogna creare un benchmark comparativo che misuri indicativamente se l'algoritmo di matching A è migliore dell'algoritmo B.

## Input:
A_input.tsv e B_input.tsv in cui ogni riga può essere una delle seguenti opzioni:

### FileA:
```bash
spotify_id \t A_youtube_url
spotify_id
```

### FileB:
```bash
spotify_id \t B_youtube_url
spotify_id
```

In cui:
`spotify_id` Id univoco della canzone su spotify (vedi il file `spot_downloader/spotify/models.py`)


## Output:
Output.tsv in cui ogni riga può essere una delle seguenti opzioni:

```bash
spotify_id \t A_youtube_url \t B_youtube_url 
spotify_id \t A_youtube_url
spotify_id \t B_youtube_url
spotify_id
```

con:
`A_youtube_url != B_youtube_url`

NOTA: Nei file NON sono presenti spazi. Io li ho inseriti per far capire meglio la struttura. Realmente sarebbe, ad esempio, così:
`spotify_id\tA_youtube_url\tB_youtube_url`


Comportamento del benchmark:
Legge l'id del file A. Cerca lo stesso id nel file B
- Se A_youtube_url AND B_youtube_url non sono presenti, appende in Output.tsv solo `spotify_id`
- Se A_youtube_url per lo stesso id `==` B_youtube_url non fa nulla e procede con gli altri spotify_id
- Se A_youtube_url per lo stesso id `!=` B_youtube_url appende in Output.tsv `spotify_id \t A_youtube_url \t B_youtube_url`
- Se A_youtube_url non è presente, appende in Output.tsv `spotify_id \t B_youtube_url`
- Se B_youtube_url non è presente, appende in Output.tsv `spotify_id \t A_youtube_url`

