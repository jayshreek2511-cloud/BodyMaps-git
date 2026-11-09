import numpy as np
from review_lung_colon_dart import hu_statistics

def test_hu_statistics_summary():
    image=np.array([-1000,-600,-200,0,100,250],dtype=np.int16)
    mask=np.array([1,1,1,1,1,0],dtype=bool)
    result=hu_statistics(image,mask)
    assert result["voxel_count"]==5
    assert result["mean"]==-340
    assert result["median"]==-200
    assert result["pct_below_m500"]==40
    assert result["pct_m200_to_100"]==60
