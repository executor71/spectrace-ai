"""Korean tokenization and BM25 are independent of vector scores and evaluation labels."""
from collections import Counter
import math,re

class KoreanTokenizer:
    def __init__(self):
        from kiwipiepy import Kiwi
        self.kiwi=Kiwi(num_workers=1)

    def __call__(self,text):
        # Preserve opaque error codes / API identifiers as complete lowercase tokens.
        identifiers=re.findall(r'[A-Za-z][A-Za-z0-9_]*',text)
        korean=[token.form.lower() for token in self.kiwi.tokenize(text)
                if re.search('[가-힣]',token.form) and token.tag.startswith(('N','V','M','XR'))]
        numbers=re.findall(r'\b\d+\b',text)
        return korean+[token.lower() for token in identifiers]+numbers

class BM25:
    def __init__(self,rows,tokenizer,k1=1.5,b=0.75):
        if k1<=0 or not 0<=b<=1:raise ValueError('Invalid BM25 parameters')
        self.rows=rows;self.tokenizer=tokenizer;self.k1=k1;self.b=b
        self.terms=[Counter(tokenizer(row['contentSnippet'])) for row in rows]
        self.lengths=[sum(t.values()) for t in self.terms]
        self.avg=sum(self.lengths)/len(rows) if rows else 0
        self.df=Counter(term for terms in self.terms for term in terms)

    def search(self,query,k):
        terms=set(self.tokenizer(query));n=len(self.rows);hits=[]
        for row,frequencies,length in zip(self.rows,self.terms,self.lengths):
            score=0.0
            for term in terms:
                frequency=frequencies.get(term,0)
                if not frequency:continue
                idf=math.log(1+(n-self.df[term]+0.5)/(self.df[term]+0.5))
                score+=idf*(frequency*(self.k1+1))/(frequency+self.k1*(1-self.b+self.b*length/(self.avg or 1)))
            if score>0:hits.append({**row,'lexicalScore':score})
        hits.sort(key=lambda row:(-row['lexicalScore'],row['chunkId']))
        return [{**row,'rank':rank} for rank,row in enumerate(hits[:k],1)]

def rrf(vector,lexical,k=60):
    if k<=0:raise ValueError('RRF k must be positive')
    combined={}
    for source,rows in [('vector',vector),('lexical',lexical)]:
        seen=set()
        for rank,row in enumerate(rows,1):
            cid=row['chunkId']
            if cid in seen:raise ValueError('Duplicate chunk in source ranking')
            seen.add(cid)
            value=combined.setdefault(cid,{**row,'fusionScore':0.0,'vectorRank':None,'lexicalRank':None})
            value['fusionScore']+=1/(k+rank);value[source+'Rank']=rank
            value[source+'Score']=row[source+'Score']
    return sorted(combined.values(),key=lambda row:(-row['fusionScore'],row['chunkId']))
