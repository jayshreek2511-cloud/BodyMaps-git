import argparse,csv,struct,zlib
from pathlib import Path
import nibabel as nib
import numpy as np
from scipy import ndimage

CASES=(3510,4934,4990,5255,6362,6444,6884,3537,40)
FONT={" ":("000","000","000","000","000"),"-":("000","000","111","000","000"),"_":("000","000","000","000","111"),":":("000","010","000","010","000"),".":("000","000","000","000","010"),
"0":("111","101","101","101","111"),"1":("010","110","010","010","111"),"2":("110","001","010","100","111"),"3":("110","001","010","001","110"),"4":("101","101","111","001","001"),"5":("111","100","110","001","110"),"6":("011","100","110","101","010"),"7":("111","001","010","010","010"),"8":("010","101","010","101","010"),"9":("010","101","011","001","110"),
"A":("010","101","111","101","101"),"B":("110","101","110","101","110"),"C":("011","100","100","100","011"),"D":("110","101","101","101","110"),"E":("111","100","110","100","111"),"F":("111","100","110","100","100"),"G":("011","100","101","101","011"),"H":("101","101","111","101","101"),"I":("111","010","010","010","111"),"J":("001","001","001","101","010"),"K":("101","101","110","101","101"),"L":("100","100","100","100","111"),"M":("101","111","111","101","101"),"N":("101","111","111","111","101"),"O":("010","101","101","101","010"),"P":("110","101","110","100","100"),"Q":("010","101","101","111","011"),"R":("110","101","110","101","101"),"S":("011","100","010","001","110"),"T":("111","010","010","010","010"),"U":("101","101","101","101","111"),"V":("101","101","101","101","010"),"W":("101","101","111","111","101"),"X":("101","101","010","101","101"),"Y":("101","101","010","010","010"),"Z":("111","001","010","100","111")}

def hu_statistics(image,mask):
 v=np.asarray(image)[np.asarray(mask,bool)].astype(float,copy=False)
 if not v.size:return dict(voxel_count=0,mean=np.nan,median=np.nan,p5=np.nan,p95=np.nan,pct_below_m500=np.nan,pct_m200_to_100=np.nan)
 return dict(voxel_count=int(v.size),mean=float(v.mean()),median=float(np.median(v)),p5=float(np.percentile(v,5)),p95=float(np.percentile(v,95)),pct_below_m500=float(np.mean(v< -500)*100),pct_m200_to_100=float(np.mean((v>=-200)&(v<=100))*100))
def zr(m,a):
 i,j,k=np.where(m)
 if not i.size:return None
 z=a[2,0]*i+a[2,1]*j+a[2,2]*k+a[2,3]
 return float(z.min()),float(z.max())
def edge(m):return m & ~ndimage.binary_erosion(m,structure=np.array([[0,1,0],[1,1,1],[0,1,0]],bool),border_value=0)
def txt(im,s):
 x=2
 for ch in s.upper():
  for y,row in enumerate(FONT.get(ch,FONT[" "])):
   for xx,b in enumerate(row):
    if b=="1" and y<im.shape[0] and x+xx<im.shape[1]:im[y,x+xx]=(255,255,255)
  x+=4
def chunk(t,d):
 q=t+d
 return struct.pack(">I",len(d))+q+struct.pack(">I",zlib.crc32(q)&0xffffffff)
def png(p,a):
 h,w,_=a.shape; raw=b"".join(b"\0"+np.ascontiguousarray(r).tobytes() for r in a)
 p.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(raw))+chunk(b"IEND",b""))
def draw(ct,m,z,win,title):
 lo,hi=(-160,240) if win=="SOFT" else (-1350,150)
 g=np.clip((ct[:,:,z].astype(float)-lo)*255/(hi-lo),0,255).astype(np.uint8)
 rgb=np.repeat(np.flipud(np.fliplr(g.T))[:,:,None],3,2)
 for k,c in (("colon",(255,230,0)),("left",(0,230,255)),("right",(255,0,220)),("dart",(0,255,0))):
  rgb[np.flipud(np.fliplr(edge(m[k][:,:,z]).T))]=c
 h=np.zeros((8,rgb.shape[1],3),np.uint8);txt(h,title);return np.concatenate((h,rgb))
def make_png(ct,m,cid,path):
 ov=m["dart"]&(m["left"]|m["right"]); counts=ov.sum((0,1)); zs=list(np.argsort(counts)[::-1][:3])+[int(np.where(m["left"]|m["right"])[2].max()) if np.any(m["left"]|m["right"]) else ct.shape[2]-1]
 panels=[]; rows=[]
 for z in zs:
  pc={k:int(a[:,:,z].sum()) for k,a in m.items()}; pc["overlap"]=int(ov[:,:,z].sum())
  label=f"{cid} Z{z} RAS AXIAL LC{pc['colon']} LL{pc['left']} LR{pc['right']} DC{pc['dart']} OL{pc['overlap']}"
  a=draw(ct,m,int(z),"SOFT",label+" SOFT L40 W400"); b=draw(ct,m,int(z),"LUNG",label+" LUNG L-600 W1500")
  panels.append(np.concatenate((a,np.zeros((a.shape[0],6,3),np.uint8),b),1))
  rows.append(dict(case_id=cid,slice_z=int(z),colon_px=pc["colon"],lung_left_px=pc["left"],lung_right_px=pc["right"],dart_colon_px=pc["dart"],overlap_px=pc["overlap"]))
 w=max(a.shape[1] for a in panels); panels=[np.pad(a,((0,0),(0,w-a.shape[1]),(0,0))) for a in panels]
 png(path,np.concatenate([np.concatenate((a,np.zeros((6,w,3),np.uint8)),0) for a in panels[:-1]]+[panels[-1]],0));return rows
def ctpath(root,n,cid):
 for p in (root/str(n)/"ct.nii.gz",root/cid/"ct.nii.gz",root/"shortlist_38"/cid/"ct.nii.gz"):
  if p.is_file():return p
 raise FileNotFoundError(f"CT missing: {cid}")
def run(out):
 base=Path(r"D:\PanTS_data"); cr=base/"ct_review"; lr=base/"labels"; pr=base/"dart_pilot_a"/"preds"; cases={}
 for n in CASES:
  cid=f"PanTS_{n:08d}"; cp=ctpath(cr,n,cid); sd=lr/cid/"segmentations"
  p={"ct":cp,"colon":sd/"colon.nii.gz","left":sd/"lung_left.nii.gz","right":sd/"lung_right.nii.gz","liver":sd/"liver.nii.gz","dart":pr/cid/"colon.nii.gz"}
  missing=[str(x) for x in p.values() if not x.is_file()]
  if missing:raise FileNotFoundError(f"{cid}: {missing}")
  ims={k:nib.as_closest_canonical(nib.load(v)) for k,v in p.items()}; ref=ims["ct"]
  bad=[k for k,v in ims.items() if v.shape!=ref.shape or not np.allclose(v.affine,ref.affine,rtol=0,atol=1e-4)]
  for k,v in p.items():print(f"{cid} {k}: {v}")
  print(f"{cid} canonical RAS grid {ref.shape}: {'MATCH' if not bad else 'MISMATCH '+str(bad)}")
  if bad:raise RuntimeError(f"Grid mismatch {cid}; stop.")
  cases[cid]=ims
 out.mkdir(parents=True,exist_ok=True); measures=[]; stats=[]; slrows=[]
 names=("A_dart_colon_and_label_lung","B_label_lung_outside_dart_colon","C_label_colon_outside_lungs","D_dart_colon_outside_label_colon")
 for cid,ims in cases.items():
  a={k:np.asarray(v.dataobj) for k,v in ims.items()}; aff=ims["ct"].affine; vm=np.prod(ims["ct"].header.get_zooms()[:3])/1000
  c=a["colon"]!=0;d=a["dart"]!=0;l=a["left"]!=0;r=a["right"]!=0;lungs=l|r;liv=a["liver"]!=0
  vol=lambda x:float(x.sum()*vm)
  measures.append(dict(case_id=cid,label_colon_ml=vol(c),dart_colon_ml=vol(d),label_lung_left_ml=vol(l),label_lung_right_ml=vol(r),dart_colon_inside_label_lung_ml=vol(d&lungs),label_colon_z_mm=zr(c,aff),dart_colon_z_mm=zr(d,aff),label_lung_left_z_mm=zr(l,aff),label_lung_right_z_mm=zr(r,aff),liver_z_mm=zr(liv,aff)))
  m={"colon":c,"left":l,"right":r,"dart":d}
  regions=(d&lungs,lungs&~d,c&~lungs,d&~c)
  for name,mask in zip(names,regions):stats.append(dict(case_id=cid,region=name,**hu_statistics(a["ct"],mask)))
  slrows+=make_png(a["ct"],m,cid,out/f"{cid}_colon_lung.png")
 def save(name,rows):
  with (out/name).open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 save("case_measurements.csv",measures);save("hu_statistics.csv",stats);save("montage_slice_counts.csv",slrows)
 print("\nCASE MEASUREMENTS");print(",".join(measures[0]))
 for x in measures:print(",".join(str(v) for v in x.values()))
 print("\nHU STATISTICS");print(",".join(stats[0]))
 for x in stats:print(",".join(str(v) for v in x.values()))
 print("Output:",out)
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--out",default=r"D:\PanTS_data\dart_pilot_a\review_images2");run(Path(ap.parse_args().out))
