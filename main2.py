from pyspark import SparkContext
import loadFiles as lf
import numpy as np
from random import randint
from  pyspark.mllib.classification import NaiveBayes
from functools import partial
from pyspark.mllib.linalg import SparseVector
from pyspark.mllib.regression import LabeledPoint

from  pyspark.mllib.classification import SVMWithSGD
from  pyspark.mllib.classification import LogisticRegressionWithLBFGS
from sklearn.cross_validation import ShuffleSplit
from sklearn.metrics import accuracy_score

#from pyspark.ml.tuning import CrossValidator
sc = SparkContext(appName="Simple App")


def createBinaryLabeledPoint(doc_class,dictionary):
	words=doc_class[0].strip().split(' ')
	#create a binary vector for the document with all the words that appear (0:does not appear,1:appears)
	#we can set in a dictionary only the indexes of the words that appear
	#and we can use that to build a SparseVector
	vector_dict={}
	for w in words:
		vector_dict[dictionary[w]]=1
	return LabeledPoint(doc_class[1], SparseVector(len(dictionary),vector_dict))

def FinalPredict(name_text,dictionary,model):
	words=name_text[1].strip().split(' ')
	vector_dict={}
	for w in words:
		if(w in dictionary):
			vector_dict[dictionary[w]]=1
	return (name_text[0], model.predict(SparseVector(len(dictionary),vector_dict)))

def createTestPoint(doc,dictionary):
	words=doc.strip().split(' ')
	vector_dict={}
	for w in words:
		if(w in dictionary):
			vector_dict[dictionary[w]]=1
	return SparseVector(len(dictionary),vector_dict)


data,Y=lf.loadLabeled("./data/train")
print "data loaded"
## cross-validaton
cv = ShuffleSplit(len(data), n_iter=3, test_size=0.3, random_state=42)
models = [NaiveBayes, LogisticRegressionWithLBFGS, SVMWithSGD]
scores = {model.__name__: [] for model in models}
for i_cv, i_temp in enumerate(cv):
	i_train = i_temp[0]
	i_test = i_temp[1]
	data_train = [data[i] for i in i_train]
	Y_train = [Y[i] for i in i_train]
	data_test = [data[i] for i in i_test]
	Y_test = [Y[i] for i in i_test]
	#print "Data samples length %d" % (len(data_train))

	dataRDD=sc.parallelize(data_train,numSlices=16)
	#map data to a binary matrix
	#1. get the dictionary of the data
	#The dictionary of each document is a list of UNIQUE(set) words 
	lists=dataRDD.map(lambda x:list(set(x.strip().split(' ')))).collect()
	all=[]
	#combine all dictionaries together (fastest solution for Python)
	for l in lists:
		all.extend(l)
	dict=set(all)
	#print "Number of words in dictionnary %d" % (len(dict))
	#it is faster to know the position of the word if we put it as values in a dictionary
	dictionary={}
	for i,word in enumerate(dict):
		dictionary[word]=i
	#we need the dictionary to be available AS A WHOLE throughout the cluster
	dict_broad=sc.broadcast(dictionary)
	#build labelled Points from data
	data_class=zip(data_train,Y_train)#if a=[1,2,3] & b=['a','b','c'] then zip(a,b)=[(1,'a'),(2, 'b'), (3, 'c')]
	dcRDD=sc.parallelize(data_class,numSlices=16)
	#get the labelled points
	labeledRDD=dcRDD.map(partial(createBinaryLabeledPoint,dictionary=dict_broad.value))

	testRDD=sc.parallelize(data_test,numSlices=16)
	testRDD2 = testRDD.map(partial(createTestPoint,dictionary=dict_broad.value))
	#print "End features extraction"

	#### Model
	
	
	for model in models:
		#### Model training
		model_trained=model.train(labeledRDD)
		#print model
		#print model.__name__
		#broadcast the model
		mb=sc.broadcast(model_trained)
		### Model testing
		Y_pred = model_trained.predict(testRDD2).collect()
		score = accuracy_score(Y_test, Y_pred)
		scores[model.__name__].append(score)
		print "Accuracy %.5f" %score

for key, value in scores.items():
	print "%s : mean=%.5f, std=%.5f " %(key, np.mean(value), np.std(value))
	# for i,model in enumerate(models):
	# 	print " %s mean accuracy_score : " accuracy_score(Y_test,Y_pred)








# #Train NaiveBayes
# model=NaiveBayes.train(labeledRDD)
# #broadcast the model
# mb=sc.broadcast(model)

# test,names=lf.loadUknown('./data/test')
# name_text=zip(names,test)
# #for each doc :(name,text):
# #apply the model on the vector representation of the text
# #return the name and the class
# predictions=sc.parallelize(name_text).map(partial(Predict,dictionary=dict_broad.value,model=mb.value)).collect()

# output=file('./classifications.txt','w')
# for x in predictions:
# 	output.write('%s\t%d\n'%x)
# output.close()

# lr=NaiveBayes()
# cv = CrossValidator(estimator=lr,numFolds=3)
# cvModel = cv.fit(labeledRDD)
# evaluator.evaluate(cvModel.transform(labeledRDD))

