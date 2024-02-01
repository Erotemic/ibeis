The job of the core of ibeis is to manage and provide data to different algorithms. These algorithms are defined in ibeis/algo. One of them is hots, which is hotspotter. It has some tweaks over the original, but the core approach is effectively the same. 

Of the the other algos in that folder only one is a search / ranking algorithm like hotspotter. That is smk, which is the "selective match kernel" (it is a bag-of-words approach). The "detect" stuff is detection work from Jason Parham, the graph is my graph algorithm to analyze and fix inconsistencies in name labeling. The "verif" is my one-vs-one approach for predicting if a pair of images is the same/different/incomparable, and "preproc" handles stuff like extracting features that other algorithms use.

